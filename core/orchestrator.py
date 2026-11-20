"""Pipeline orchestrator with fraud escalation route and shared OrderState management."""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
from agent_framework.ollama import OllamaChatClient
from dotenv import load_dotenv

from agents.dispatch_agent import (
    AGENT_NAME as DISPATCH_NAME,
    AGENT_ROLE as DISPATCH_ROLE,
    AGENT_TOOLS as DISPATCH_TOOLS,
    run_dispatch_agent,
)
from agents.fraud_agent import (
    AGENT_NAME as FRAUD_NAME,
    AGENT_ROLE as FRAUD_ROLE,
    AGENT_TOOLS as FRAUD_TOOLS,
    run_fraud_agent,
)
from agents.inventory_agent import (
    AGENT_NAME as INVENTORY_NAME,
    AGENT_ROLE as INVENTORY_ROLE,
    AGENT_TOOLS as INVENTORY_TOOLS,
    run_inventory_agent,
)
from agents.pricing_agent import (
    AGENT_NAME as PRICING_NAME,
    AGENT_ROLE as PRICING_ROLE,
    AGENT_TOOLS as PRICING_TOOLS,
    run_pricing_agent,
)
from agents.validation_agent import (
    AGENT_NAME as VALIDATION_NAME,
    AGENT_ROLE as VALIDATION_ROLE,
    AGENT_TOOLS as VALIDATION_TOOLS,
    run_validation_agent,
)
from core.order_state import ExecutionLogger, OrderState
from memory.database import DatabaseManager
from tools.business_tools import BusinessRulesConfig, BusinessToolkit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

AGENT_ROSTER = [
    {"stage": 1, "name": VALIDATION_NAME, "module": "agents/validation_agent.py", "role": VALIDATION_ROLE, "tools": VALIDATION_TOOLS},
    {"stage": 2, "name": INVENTORY_NAME, "module": "agents/inventory_agent.py", "role": INVENTORY_ROLE, "tools": INVENTORY_TOOLS},
    {"stage": 3, "name": FRAUD_NAME, "module": "agents/fraud_agent.py", "role": FRAUD_ROLE, "tools": FRAUD_TOOLS},
    {"stage": 4, "name": PRICING_NAME, "module": "agents/pricing_agent.py", "role": PRICING_ROLE, "tools": PRICING_TOOLS},
    {"stage": 5, "name": DISPATCH_NAME, "module": "agents/dispatch_agent.py", "role": DISPATCH_ROLE, "tools": DISPATCH_TOOLS},
]


def check_ollama_health(host: str, model_id: str, timeout: float = 2.5) -> tuple[bool, str]:
    """Check whether local Ollama server is reachable and whether model_id is installed."""
    url = f"{host.rstrip('/')}/api/tags"
    try:
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        models = [m.get("name", "") for m in payload.get("models", [])]
        if any(m == model_id or m.startswith(f"{model_id}:") for m in models):
            return True, f"Ollama online at {host} with model '{model_id}'."
        return (
            False,
            f"Ollama online at {host}, but model '{model_id}' not found (available: {', '.join(models) or 'none'}).",
        )
    except Exception as exc:
        return False, f"Ollama unreachable at {host}: {exc}"


class OrderFulfilmentOrchestrator:
    """Coordinates the five agents sequentially with a deterministic fraud-escalation gate."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        products_json_path: Path | str | None = None,
        log_path: Path | str | None = None,
        rules_config: BusinessRulesConfig | None = None,
        ollama_host: str | None = None,
        ollama_model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.db_path = Path(db_path or PROJECT_ROOT / "memory" / "orders.db")
        self.products_json_path = Path(products_json_path or PROJECT_ROOT / "data" / "products.json")
        self.log_path = Path(log_path or PROJECT_ROOT / "logs" / "execution.jsonl")

        self.db = DatabaseManager(self.db_path, self.products_json_path)
        self.logger = ExecutionLogger(self.log_path)
        self.rules = rules_config or BusinessRulesConfig.from_env()
        self.toolkit = BusinessToolkit(self.db, self.logger, self.rules)

        self.ollama_host = ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL_ID", "qwen3:4b")
        self.timeout_seconds = float(timeout_seconds or os.getenv("OLLAMA_TIMEOUT_SECONDS", "35"))

    def ollama_status(self) -> tuple[bool, str]:
        return check_ollama_health(self.ollama_host, self.ollama_model)

    def _create_ollama_client(self) -> OllamaChatClient:
        return OllamaChatClient(host=self.ollama_host, model=self.ollama_model)

    def _record_orchestrator_event(
        self, state: OrderState, action: str, result: str, explanation: str
    ) -> None:
        entry = state.add_trace(
            agent_name="Orchestrator",
            action=action,
            tool_used="pipeline_guard",
            result=result,
            explanation=explanation,
        )
        self.logger.append(entry)

    async def process_order_async(
        self,
        customer_id: str,
        customer_name: str,
        product_id: str,
        quantity: int,
        address: str,
        payment_status: str,
        customer_phone: str = "",
        order_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        mode: Optional[str] = None,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> OrderState:
        """Run an incoming order end-to-end through the 5-agent pipeline with hard gates."""
        requested_mode = (mode or os.getenv("EXECUTION_MODE", "OLLAMA")).strip().upper()
        if requested_mode not in {"OLLAMA", "DEMO"}:
            requested_mode = "DEMO"

        # Duplicate submission guard (prevents double stock deductions on repeated clicks)
        # Allow re-processing if an order is explicitly transitioning out of PENDING_REVIEW.
        if idempotency_key:
            existing = self.db.get_order_by_idempotency_key(idempotency_key)
            if existing and existing.get("decision") != "PENDING_REVIEW":
                dup_state = OrderState(
                    order_id=existing["order_id"],
                    customer_id=existing["customer_id"],
                    customer_name=existing.get("customer_name") or "",
                    address=existing.get("address") or "",
                    payment_status=existing.get("payment_status") or "",
                    validation_status=existing.get("validation_status") or "PENDING",
                    inventory_status=existing.get("inventory_status") or "PENDING",
                    fraud_status=existing.get("fraud_status") or "PENDING",
                    pricing_status=existing.get("pricing_status") or "PENDING",
                    dispatch_status=existing.get("dispatch_status") or "PENDING",
                    fraud_score=int(existing.get("fraud_score") or 0),
                    subtotal=float(existing.get("subtotal") or 0.0),
                    discount=float(existing.get("discount") or 0.0),
                    tax=float(existing.get("tax") or 0.0),
                    final_total=float(existing.get("final_total") or 0.0),
                    shipping_method=existing.get("shipping_method"),
                    tracking_id=existing.get("tracking_id"),
                    decision=existing.get("decision") or "PENDING",
                    hold_reason=existing.get("hold_reason")
                    or "Duplicate submission ignored; returning original order result.",
                    execution_mode=existing.get("execution_mode") or requested_mode,
                    idempotency_key=idempotency_key,
                )
                self._record_orchestrator_event(
                    dup_state,
                    "duplicate_check",
                    "DUPLICATE_IGNORED",
                    f"Duplicate submission for idempotency_key='{idempotency_key}' blocked; returning existing order {existing['order_id']}.",
                )
                return dup_state

        resolved_order_id = order_id or f"ORD-{uuid.uuid4().hex[:8].upper()}"
        product = self.db.get_product(product_id)
        item_record = {
            "product_id": product_id,
            "product_name": product["name"] if product else "Unknown Product",
            "quantity": int(quantity),
            "unit_price": float(product["price"]) if product else 0.0,
        }

        # Determine effective execution mode transparently
        client: Optional[OllamaChatClient] = None
        effective_mode = requested_mode
        fallback_note = ""
        if requested_mode == "OLLAMA":
            ok, health_msg = self.ollama_status()
            if ok:
                client = self._create_ollama_client()
            else:
                effective_mode = "DEMO"
                fallback_note = (
                    f"Ollama unavailable ({health_msg}). transparently switched to deterministic DEMO MODE "
                    "(no LLM invoked)."
                )

        state = OrderState(
            order_id=resolved_order_id,
            customer_id=customer_id.strip(),
            customer_name=customer_name.strip() or f"Customer {customer_id.strip()}",
            customer_phone=customer_phone.strip(),
            items=[item_record],
            address=address.strip(),
            payment_status=payment_status.strip().upper(),
            execution_mode=effective_mode,
            idempotency_key=idempotency_key or resolved_order_id,
        )
        self.toolkit.register_state(state)

        self._record_orchestrator_event(
            state,
            "workflow_started",
            effective_mode,
            fallback_note
            or f"Started 5-agent fulfilment workflow in {effective_mode} mode for {state.order_id}.",
        )

        def _notify(stage: str, status: str) -> None:
            if progress_callback:
                progress_callback(stage, status)

        try:
            # --- STAGE 1: VALIDATION AGENT ---
            _notify(VALIDATION_NAME, "RUNNING")
            await self._run_stage_with_fallback(
                run_validation_agent, VALIDATION_NAME, state, client, effective_mode
            )
            _notify(VALIDATION_NAME, state.validation_status)

            if state.validation_status != "VALID":
                state.decision = "REJECTED"
                state.dispatch_status = "NOT_DISPATCHED"
                state.pricing_status = "SKIPPED"
                state.hold_reason = "; ".join(state.validation_reasons) or "Order failed mandatory validation."
                self._record_orchestrator_event(
                    state, "pipeline_stop", "REJECTED", f"Stopped after Validation Agent: {state.hold_reason}"
                )
                self.db.save_order(state)
                return state

            # --- STAGE 2: INVENTORY AGENT ---
            _notify(INVENTORY_NAME, "RUNNING")
            await self._run_stage_with_fallback(
                run_inventory_agent, INVENTORY_NAME, state, client, effective_mode
            )
            _notify(INVENTORY_NAME, state.inventory_status)

            if state.inventory_status != "RESERVED":
                state.decision = "SHORTFALL"
                state.dispatch_status = "NOT_DISPATCHED"
                state.pricing_status = "SKIPPED"
                sub_text = (
                    f" Suggested substitute: {state.substitute_suggestion['product_id']} ({state.substitute_suggestion['name']})."
                    if state.substitute_suggestion
                    else ""
                )
                state.hold_reason = f"Insufficient stock for {product_id} (qty {quantity}).{sub_text}"
                self._record_orchestrator_event(
                    state, "pipeline_stop", "SHORTFALL", f"Stopped after Inventory Agent: {state.hold_reason}"
                )
                self.db.save_order(state)
                return state

            # --- STAGE 3: FRAUD CHECK AGENT (WITH ESCALATION ROUTE) ---
            _notify(FRAUD_NAME, "RUNNING")
            await self._run_stage_with_fallback(
                run_fraud_agent, FRAUD_NAME, state, client, effective_mode
            )
            _notify(FRAUD_NAME, state.fraud_status)

            should_hold = state.fraud_status == "HIGH" or (
                state.fraud_status == "MEDIUM" and self.rules.hold_on_medium_risk
            )
            if should_hold:
                state.decision = "HELD_FOR_REVIEW"
                state.dispatch_status = "HELD"
                state.pricing_status = "SKIPPED"
                state.hold_reason = (
                    f"Fraud escalation triggered (Risk: {state.fraud_status}, Score: {state.fraud_score}/100). "
                    + ("; ".join(state.fraud_reasons) if state.fraud_reasons else "High risk threshold exceeded.")
                    + " Reserved stock held pending manual review."
                )
                self._record_orchestrator_event(
                    state,
                    "fraud_escalation",
                    "HELD_FOR_REVIEW",
                    state.hold_reason,
                )
                self.db.save_order(state)
                return state

            # --- STAGE 4: PRICING AGENT ---
            _notify(PRICING_NAME, "RUNNING")
            await self._run_stage_with_fallback(
                run_pricing_agent, PRICING_NAME, state, client, effective_mode
            )
            _notify(PRICING_NAME, state.pricing_status)

            if state.pricing_status != "PRICED":
                state.decision = "ERROR"
                state.dispatch_status = "NOT_DISPATCHED"
                state.hold_reason = "Pricing stage did not complete cleanly."
                self._record_orchestrator_event(
                    state, "pipeline_stop", "ERROR", state.hold_reason
                )
                self.db.save_order(state)
                return state

            # --- STAGE 5: DISPATCH COORDINATOR ---
            _notify(DISPATCH_NAME, "RUNNING")
            await self._run_stage_with_fallback(
                run_dispatch_agent, DISPATCH_NAME, state, client, effective_mode
            )
            _notify(DISPATCH_NAME, state.dispatch_status)

            self.db.save_order(state)
            return state

        except Exception as exc:
            state.decision = "ERROR"
            state.dispatch_status = "NOT_DISPATCHED"
            state.hold_reason = f"Unexpected pipeline exception: {exc}"
            self._record_orchestrator_event(state, "pipeline_exception", "ERROR", state.hold_reason)
            self.db.save_order(state)
            return state

    async def _run_stage_with_fallback(
        self,
        runner: Callable[..., Any],
        agent_name: str,
        state: OrderState,
        client: Optional[OllamaChatClient],
        effective_mode: str,
    ) -> str:
        """Run an agent in OLLAMA mode with timeout protection; fall back transparently on LLM error."""
        if effective_mode == "OLLAMA" and client is not None:
            try:
                return await runner(
                    state,
                    self.toolkit,
                    client=client,
                    mode="OLLAMA",
                    timeout_seconds=self.timeout_seconds,
                )
            except Exception as exc:
                self._record_orchestrator_event(
                    state,
                    "llm_fallback",
                    "DEMO_FALLBACK",
                    f"{agent_name} Ollama call failed/timed out ({exc}); completing stage in deterministic DEMO MODE.",
                )
                state.execution_mode = "DEMO"
                return await runner(state, self.toolkit, client=None, mode="DEMO")

        return await runner(state, self.toolkit, client=None, mode="DEMO")

    def submit_customer_order(
        self,
        customer_id: str,
        customer_name: str,
        customer_phone: str,
        product_id: str,
        quantity: int,
        address: str,
        payment_status: str,
        idempotency_key: Optional[str] = None,
    ) -> OrderState:
        """Queue a customer storefront order as PENDING_REVIEW for Admin 5-agent verification."""
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        product = self.db.get_product(product_id)
        unit_price = float(product["price"]) if product else 0.0
        subtotal = round(unit_price * int(quantity), 2)

        state = OrderState(
            order_id=order_id,
            customer_id=customer_id.strip(),
            customer_name=customer_name.strip() or f"Customer {customer_id.strip()}",
            customer_phone=customer_phone.strip(),
            items=[
                {
                    "product_id": product_id,
                    "product_name": product["name"] if product else "Unknown Product",
                    "quantity": int(quantity),
                    "unit_price": unit_price,
                }
            ],
            address=address.strip(),
            payment_status=payment_status.strip().upper(),
            subtotal=subtotal,
            decision="PENDING_REVIEW",
            hold_reason="Awaiting Admin 5-Agent Verification & Dispatch Approval.",
            execution_mode="STOREFRONT",
            idempotency_key=idempotency_key or order_id,
        )
        self._record_orchestrator_event(
            state,
            "customer_checkout",
            "PENDING_REVIEW",
            f"Customer {state.customer_name} ({state.customer_id}) placed storefront order for {quantity}x {product_id}; queued for Admin AI verification.",
        )
        self.db.save_order(state)
        return state

    def process_pending_order(
        self,
        order_id: str,
        mode: Optional[str] = None,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> OrderState:
        """Run the 5-agent fulfilment pipeline on an existing PENDING_REVIEW storefront order."""
        details = self.db.get_order_details(order_id)
        if not details or not details.get("items"):
            raise ValueError(f"Pending order '{order_id}' not found.")
        item = details["items"][0]
        return self.process_order(
            customer_id=details["customer_id"],
            customer_name=details.get("customer_name") or "",
            customer_phone=details.get("customer_phone") or "",
            product_id=item["product_id"],
            quantity=int(item["quantity"]),
            address=details.get("address") or "",
            payment_status=details.get("payment_status") or "UNPAID",
            order_id=order_id,
            idempotency_key=details.get("idempotency_key") or order_id,
            mode=mode,
            progress_callback=progress_callback,
        )

    def admin_resolve_held_order(
        self, order_id: str, action: str, admin_note: str = ""
    ) -> OrderState:
        """Human-in-the-loop admin resolution for HELD_FOR_REVIEW fraud orders."""
        details = self.db.get_order_details(order_id)
        if not details or not details.get("items"):
            raise ValueError(f"Held order '{order_id}' not found.")
        item = details["items"][0]

        state = OrderState(
            order_id=details["order_id"],
            customer_id=details["customer_id"],
            customer_name=details.get("customer_name") or "",
            customer_phone=details.get("customer_phone") or "",
            items=[
                {
                    "product_id": item["product_id"],
                    "product_name": item.get("product_name") or item["product_id"],
                    "quantity": int(item["quantity"]),
                    "unit_price": float(item["unit_price"]),
                }
            ],
            address=details.get("address") or "",
            payment_status=details.get("payment_status") or "PAID",
            validation_status=details.get("validation_status") or "VALID",
            inventory_status=details.get("inventory_status") or "RESERVED",
            fraud_status=details.get("fraud_status") or "HIGH",
            pricing_status=details.get("pricing_status") or "SKIPPED",
            dispatch_status=details.get("dispatch_status") or "HELD",
            fraud_score=int(details.get("fraud_score") or 0),
            decision=details.get("decision") or "HELD_FOR_REVIEW",
            hold_reason=details.get("hold_reason"),
            execution_mode="ADMIN_REVIEW",
            idempotency_key=details.get("idempotency_key") or order_id,
            created_at=details.get("created_at") or "",
        )
        self.toolkit.register_state(state)

        choice = action.strip().upper()
        if choice == "APPROVE":
            # Admin overrides fraud hold -> mark fraud cleared by human review, run Pricing + Dispatch
            state.fraud_status = "LOW"
            state.hold_reason = None
            self._record_orchestrator_event(
                state,
                "admin_fraud_override",
                "APPROVED",
                f"Admin manually verified customer/order and approved dispatch. Note: {admin_note or 'Verified via phone/ID check.'}",
            )
            self.toolkit.get_product_price(state.order_id, item["product_id"])
            self.toolkit.calculate_discount(state.order_id, state.subtotal)
            self.toolkit.calculate_final_total(
                state.order_id, state.subtotal, state.discount, self.rules.tax_rate
            )
            self.toolkit.select_shipping_method(state.order_id, state.address)
            self.toolkit.generate_tracking_id(state.order_id)
            self.toolkit.confirm_dispatch(state.order_id)
            self.db.save_order(state)
            return state

        # Reject confirmed fraud and automatically release reserved inventory back to stock
        if state.inventory_status == "RESERVED":
            new_stock = self.db.release_stock(item["product_id"], int(item["quantity"]))
            stock_msg = f" Released {item['quantity']} unit(s) of {item['product_id']} back to inventory (stock now {new_stock})."
        else:
            stock_msg = ""

        state.decision = "REJECTED"
        state.dispatch_status = "NOT_DISPATCHED"
        state.inventory_status = "RELEASED"
        state.hold_reason = (
            f"Admin confirmed fraud & rejected order. {admin_note}".strip() + stock_msg
        )
        self._record_orchestrator_event(
            state,
            "admin_fraud_reject",
            "REJECTED",
            state.hold_reason,
        )
        self.db.save_order(state)
        return state

    def process_order(self, **kwargs: Any) -> OrderState:
        """Synchronous wrapper safe for CLI, Streamlit, and Jupyter (active event loop safe)."""
        coro = self.process_order_async(**kwargs)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        # Already inside a running event loop (e.g., Jupyter cell calling sync API)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
