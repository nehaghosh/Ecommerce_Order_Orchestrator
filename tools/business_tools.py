"""Real deterministic Python tools for all five order-fulfilment agents.

All tool functions accept flat primitive arguments (str, int, float) so small local
LLMs (such as Ollama qwen3:4b) can invoke them reliably without malformed nested JSON,
while reading and updating the shared OrderState and SQLite database deterministically.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from core.order_state import ExecutionLogger, OrderState
from memory.database import DatabaseManager


@dataclass
class BusinessRulesConfig:
    """Configurable demonstration assumptions (loaded from environment or defaults)."""

    discount_threshold: float = 3000.0
    discount_rate: float = 0.05
    tax_rate: float = 0.18
    high_order_value_threshold: float = 5000.0
    fraud_hold_threshold: int = 60
    hold_on_medium_risk: bool = False

    @classmethod
    def from_env(cls) -> "BusinessRulesConfig":
        return cls(
            discount_threshold=float(os.getenv("DISCOUNT_THRESHOLD", "3000.0")),
            discount_rate=float(os.getenv("DISCOUNT_RATE", "0.05")),
            tax_rate=float(os.getenv("TAX_RATE", "0.18")),
            high_order_value_threshold=float(os.getenv("HIGH_ORDER_VALUE_THRESHOLD", "5000.0")),
            fraud_hold_threshold=int(os.getenv("FRAUD_HOLD_THRESHOLD", "60")),
            hold_on_medium_risk=os.getenv("HOLD_ON_MEDIUM_RISK", "false").strip().lower()
            in {"1", "true", "yes"},
        )


class BusinessToolkit:
    """Binds shared OrderState registry, SQLite DB, and append-only logger to agent tools."""

    METRO_CITIES = (
        "bengaluru",
        "bangalore",
        "mumbai",
        "delhi",
        "new delhi",
        "hyderabad",
        "chennai",
        "pune",
        "kolkata",
        "noida",
        "gurugram",
        "gurgaon",
        "chandigarh",
    )

    def __init__(
        self,
        db: DatabaseManager,
        logger: ExecutionLogger,
        config: BusinessRulesConfig | None = None,
    ) -> None:
        self.db = db
        self.logger = logger
        self.config = config or BusinessRulesConfig.from_env()
        self._states: dict[str, OrderState] = {}

    def register_state(self, state: OrderState) -> None:
        self._states[state.order_id] = state

    def get_state(self, order_id: str) -> OrderState:
        if order_id not in self._states:
            raise KeyError(f"OrderState not found for order_id={order_id}")
        return self._states[order_id]

    def _record(
        self,
        state: OrderState,
        agent_name: str,
        action: str,
        tool_used: str,
        result: str,
        explanation: str,
    ) -> None:
        entry = state.add_trace(
            agent_name=agent_name,
            action=action,
            tool_used=tool_used,
            result=result,
            explanation=explanation,
        )
        self.logger.append(entry)

    # =====================================================================
    # AGENT 1: VALIDATION AGENT TOOLS
    # =====================================================================

    def check_product_exists(self, order_id: str, product_id: str) -> str:
        """Verify that product_id exists in the SQLite catalog and requested quantity > 0."""
        state = self.get_state(order_id)
        item = state.primary_item
        target_pid = (product_id or item.get("product_id", "")).strip()
        qty = int(item.get("quantity", 0))

        product = self.db.get_product(target_pid)
        if not product:
            reason = f"Product '{target_pid}' does not exist in the catalog."
            if reason not in state.validation_reasons:
                state.validation_reasons.append(reason)
            state.validation_status = "INVALID"
            self._record(
                state, "Validation Agent", "check_product", "check_product_exists", "INVALID", reason
            )
            return json.dumps({"exists": False, "product_id": target_pid, "reason": reason})

        if qty <= 0:
            reason = f"Invalid quantity ({qty}) requested for product {target_pid}; must be >= 1."
            if reason not in state.validation_reasons:
                state.validation_reasons.append(reason)
            state.validation_status = "INVALID"
            self._record(
                state, "Validation Agent", "check_product", "check_product_exists", "INVALID", reason
            )
            return json.dumps({"exists": True, "valid_quantity": False, "reason": reason})

        # Populate authoritative product name and unit price onto shared state
        if state.items:
            state.items[0]["product_name"] = product["name"]
            state.items[0]["unit_price"] = float(product["price"])

        msg = f"Product {product['product_id']} ({product['name']}) verified at INR {product['price']:.2f} x {qty}."
        self._record(state, "Validation Agent", "check_product", "check_product_exists", "VALID", msg)
        return json.dumps(
            {
                "exists": True,
                "valid_quantity": True,
                "product_id": product["product_id"],
                "product_name": product["name"],
                "unit_price": float(product["price"]),
                "quantity": qty,
            }
        )

    SPAM_MARKERS = ("spam", "fake", "asdfgh", "qwerty", "test1234", "dummy address", "xxx")

    def validate_address(self, order_id: str, address: str) -> str:
        """Validate delivery address, contact number (if supplied), and basic anti-spam patterns."""
        state = self.get_state(order_id)
        addr = (state.address or address or "").strip()
        phone = (state.customer_phone or "").strip()
        lower_text = f"{addr} {state.customer_name}".lower()

        issues: list[str] = []
        if len(addr) < 10 or len(addr.split()) < 2:
            issues.append(
                "Delivery address is missing or incomplete (minimum 10 characters and street/city required)."
            )

        if any(marker in lower_text for marker in self.SPAM_MARKERS) or re.search(
            r"(.)\1{4,}", addr.lower()
        ):
            issues.append("Order flagged as potential spam/invalid gibberish in address or customer name.")

        if phone:
            digits = re.sub(r"\D", "", phone)
            if len(digits) < 10 or len(digits) > 13 or len(set(digits)) <= 2:
                issues.append(
                    f"Contact phone '{phone}' is invalid (expected valid 10-digit mobile number)."
                )

        if issues:
            reason = " ".join(issues)
            if reason not in state.validation_reasons:
                state.validation_reasons.append(reason)
            state.validation_status = "INVALID"
            self._record(
                state, "Validation Agent", "validate_address", "validate_address", "INVALID", reason
            )
            return json.dumps({"valid": False, "reason": reason})

        phone_note = f" | Contact verified: {phone}" if phone else ""
        msg = f"Delivery address & anti-spam checks passed: {addr}{phone_note}"
        self._record(state, "Validation Agent", "validate_address", "validate_address", "VALID", msg)
        return json.dumps({"valid": True, "address": addr, "contact_verified": bool(phone)})

    def verify_payment(self, order_id: str, payment_status: str) -> str:
        """Verify that payment has been completed (PAID) before fulfilment."""
        state = self.get_state(order_id)
        status = (state.payment_status or payment_status or "").strip().upper()

        if status != "PAID":
            reason = f"Payment status is '{status or 'MISSING'}'; order cannot proceed unless PAID."
            if reason not in state.validation_reasons:
                state.validation_reasons.append(reason)
            state.validation_status = "INVALID"
            self._record(
                state, "Validation Agent", "verify_payment", "verify_payment", "INVALID", reason
            )
            return json.dumps({"payment_verified": False, "payment_status": status, "reason": reason})

        msg = "Payment status confirmed as PAID."
        self._record(state, "Validation Agent", "verify_payment", "verify_payment", "VALID", msg)
        return json.dumps({"payment_verified": True, "payment_status": status})

    # =====================================================================
    # AGENT 2: INVENTORY AGENT TOOLS
    # =====================================================================

    def get_stock_level(self, order_id: str, product_id: str) -> str:
        """Return current available stock for a product from SQLite."""
        state = self.get_state(order_id)
        pid = state.primary_item.get("product_id", product_id)
        qty = int(state.primary_item.get("quantity", 0))
        product = self.db.get_product(pid)

        if not product:
            msg = f"Product {pid} not found during stock check."
            state.inventory_status = "SHORTFALL"
            self._record(state, "Inventory Agent", "check_stock", "get_stock_level", "SHORTFALL", msg)
            return json.dumps({"product_id": pid, "available_stock": 0, "sufficient": False})

        available = int(product["stock"])
        sufficient = available >= qty and qty > 0
        status = "AVAILABLE" if sufficient else "INSUFFICIENT"
        msg = f"{product['name']} ({pid}) has {available} unit(s) in stock; requested {qty}."
        self._record(state, "Inventory Agent", "check_stock", "get_stock_level", status, msg)
        return json.dumps(
            {
                "product_id": pid,
                "product_name": product["name"],
                "available_stock": available,
                "requested_quantity": qty,
                "sufficient": sufficient,
            }
        )

    def reserve_stock(self, order_id: str, product_id: str, quantity: int) -> str:
        """Atomically reserve requested stock in SQLite without ever allowing negative inventory."""
        state = self.get_state(order_id)
        pid = state.primary_item.get("product_id", product_id)
        qty = int(state.primary_item.get("quantity", quantity))

        # Idempotency guard: prevent double-deduction if LLM invokes this tool twice
        if state.inventory_status == "RESERVED":
            prod = self.db.get_product(pid)
            remaining = int(prod["stock"]) if prod else 0
            return json.dumps(
                {
                    "reserved": True,
                    "already_reserved": True,
                    "product_id": pid,
                    "quantity": qty,
                    "remaining_stock": remaining,
                }
            )

        success, remaining = self.db.reserve_stock(pid, qty)
        if success:
            state.inventory_status = "RESERVED"
            msg = f"Reserved {qty} unit(s) of {pid}. Remaining stock: {remaining}."
            self._record(state, "Inventory Agent", "reserve_stock", "reserve_stock", "RESERVED", msg)
            return json.dumps(
                {
                    "reserved": True,
                    "product_id": pid,
                    "quantity": qty,
                    "remaining_stock": remaining,
                }
            )

        state.inventory_status = "SHORTFALL"
        msg = f"Stock shortfall for {pid}: requested {qty}, available {remaining}. Stock unchanged."
        self._record(state, "Inventory Agent", "reserve_stock", "reserve_stock", "SHORTFALL", msg)
        return json.dumps(
            {
                "reserved": False,
                "product_id": pid,
                "requested_quantity": qty,
                "available_stock": remaining,
            }
        )

    def suggest_substitute(self, order_id: str, product_id: str) -> str:
        """Suggest an available substitute product when requested stock cannot be fulfilled."""
        state = self.get_state(order_id)
        pid = state.primary_item.get("product_id", product_id)
        substitute = self.db.get_substitute_product(pid)

        if substitute:
            state.substitute_suggestion = {
                "product_id": substitute["product_id"],
                "name": substitute["name"],
                "price": float(substitute["price"]),
                "stock": int(substitute["stock"]),
            }
            msg = (
                f"Suggested substitute for {pid}: {substitute['product_id']} "
                f"({substitute['name']}) at INR {substitute['price']:.2f} "
                f"({substitute['stock']} in stock)."
            )
            self._record(
                state, "Inventory Agent", "suggest_substitute", "suggest_substitute", "SUGGESTED", msg
            )
            return json.dumps({"substitute_found": True, "substitute": state.substitute_suggestion})

        msg = f"No in-stock substitute available for {pid}; item can be backordered."
        self._record(
            state, "Inventory Agent", "suggest_substitute", "suggest_substitute", "BACKORDER", msg
        )
        return json.dumps({"substitute_found": False, "recommendation": "Backorder"})

    # =====================================================================
    # AGENT 3: FRAUD CHECK AGENT TOOLS
    # =====================================================================

    def get_customer_history(self, order_id: str, customer_id: str) -> str:
        """Retrieve persistent prior-order history and fraud flags from SQLite."""
        state = self.get_state(order_id)
        cid = state.customer_id or customer_id
        history = self.db.get_customer_history(cid, exclude_order_id=state.order_id)
        state.customer_history_summary = history

        msg = (
            f"Retrieved history for {cid} ({history['customer_name']}): "
            f"{history['total_prior_orders']} prior order(s), "
            f"{history['failed_payments']} failed payment(s), "
            f"{history['cancelled_orders']} cancellation(s), "
            f"{history['prior_fraud_flags']} prior fraud flag(s)."
        )
        self._record(
            state, "Fraud Check Agent", "retrieve_memory", "get_customer_history", "RETRIEVED", msg
        )
        return json.dumps(history)

    def calculate_fraud_score(self, order_id: str, customer_id: str) -> str:
        """Calculate a deterministic demonstration fraud score (0-100) using SQLite memory."""
        state = self.get_state(order_id)
        cid = state.customer_id or customer_id
        history = state.customer_history_summary or self.db.get_customer_history(
            cid, exclude_order_id=state.order_id
        )
        state.customer_history_summary = history

        order_value = state.estimated_order_value
        score = 0
        reasons: list[str] = []

        if history["failed_payments"] >= 2:
            score += 30
            reasons.append(f"Multiple prior failed payments ({history['failed_payments']}): +30")

        if history["prior_fraud_flags"] >= 1:
            score += 30
            reasons.append(f"Prior fraud flag(s) on record ({history['prior_fraud_flags']}): +30")

        if order_value >= self.config.high_order_value_threshold:
            score += 25
            reasons.append(
                f"High order value INR {order_value:.2f} >= INR {self.config.high_order_value_threshold:.2f}: +25"
            )

        if history["cancelled_orders"] >= 2:
            score += 20
            reasons.append(f"Repeated cancelled orders ({history['cancelled_orders']}): +20")

        if (
            history["total_prior_orders"] == 0
            and order_value >= self.config.high_order_value_threshold
        ):
            score += 15
            reasons.append("New customer (0 prior orders) with high-value order: +15")

        score = max(0, min(100, score))

        if score >= self.config.fraud_hold_threshold:
            risk_level = "HIGH"
        elif score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        state.fraud_score = score
        state.fraud_status = risk_level
        state.fraud_reasons = reasons

        explanation = (
            f"Fraud score = {score}/100 ({risk_level}). "
            + ("; ".join(reasons) if reasons else "No risk rules triggered.")
        )
        self._record(
            state,
            "Fraud Check Agent",
            "score_fraud_risk",
            "calculate_fraud_score",
            risk_level,
            explanation,
        )
        return json.dumps(
            {
                "order_id": state.order_id,
                "customer_id": cid,
                "order_value": order_value,
                "fraud_score": score,
                "risk_level": risk_level,
                "reasons": reasons,
                "demo_rule_disclaimer": "Configurable demonstration scoring rules only.",
            }
        )

    def record_fraud_flag(self, order_id: str, customer_id: str, reason: str) -> str:
        """Persist a fraud flag in SQLite when risk is MEDIUM or HIGH."""
        state = self.get_state(order_id)
        cid = state.customer_id or customer_id

        # Prevent duplicate flag inserts during a single order run
        already_flagged = any(
            t.get("tool_used") == "record_fraud_flag" and t.get("result") == "FLAGGED"
            for t in state.execution_trace
        )
        if already_flagged:
            return json.dumps({"flagged": True, "already_recorded": True, "order_id": state.order_id})

        flag_reason = reason.strip() if reason and reason.strip() else "; ".join(state.fraud_reasons)
        if not flag_reason:
            flag_reason = f"Elevated fraud risk score ({state.fraud_score}/100)"

        record = self.db.record_fraud_flag(cid, state.order_id, flag_reason, state.fraud_score)
        msg = f"Fraud flag #{record['flag_id']} recorded in SQLite for {cid} ({state.fraud_status}): {flag_reason}"
        self._record(
            state, "Fraud Check Agent", "record_fraud_flag", "record_fraud_flag", "FLAGGED", msg
        )
        return json.dumps({"flagged": True, "record": record})

    # =====================================================================
    # AGENT 4: PRICING AGENT TOOLS (100% DETERMINISTIC)
    # =====================================================================

    def get_product_price(self, order_id: str, product_id: str) -> str:
        """Retrieve authoritative unit price and compute deterministic subtotal."""
        state = self.get_state(order_id)
        pid = state.primary_item.get("product_id", product_id)
        qty = int(state.primary_item.get("quantity", 1))
        product = self.db.get_product(pid)

        if not product:
            msg = f"Unable to retrieve price: product {pid} not found."
            self._record(state, "Pricing Agent", "get_price", "get_product_price", "ERROR", msg)
            return json.dumps({"found": False, "product_id": pid})

        unit_price = float(product["price"])
        if state.items:
            state.items[0]["unit_price"] = unit_price
            state.items[0]["product_name"] = product["name"]
        subtotal = round(unit_price * qty, 2)
        state.subtotal = subtotal

        msg = f"Unit price for {pid} ({product['name']}) = INR {unit_price:.2f} x {qty} -> Subtotal INR {subtotal:.2f}."
        self._record(state, "Pricing Agent", "get_price", "get_product_price", "OK", msg)
        return json.dumps(
            {
                "found": True,
                "product_id": pid,
                "unit_price": unit_price,
                "quantity": qty,
                "subtotal": subtotal,
            }
        )

    def calculate_discount(self, order_id: str, subtotal: float) -> str:
        """Deterministically apply configurable sample discount (5% if subtotal >= INR 3,000)."""
        state = self.get_state(order_id)
        # Always rely on authoritative state.subtotal so LLM cannot alter numbers
        auth_subtotal = state.subtotal if state.subtotal > 0 else state.estimated_order_value
        state.subtotal = round(auth_subtotal, 2)

        if state.subtotal >= self.config.discount_threshold:
            discount = round(state.subtotal * self.config.discount_rate, 2)
            rule = (
                f"{int(self.config.discount_rate * 100)}% demo discount applied "
                f"(subtotal >= INR {self.config.discount_threshold:.2f})."
            )
        else:
            discount = 0.0
            rule = (
                f"No discount applied (subtotal INR {state.subtotal:.2f} "
                f"< threshold INR {self.config.discount_threshold:.2f})."
            )

        state.discount = discount
        msg = f"Discount calculated: INR {discount:.2f}. {rule}"
        self._record(state, "Pricing Agent", "calculate_discount", "calculate_discount", "OK", msg)
        return json.dumps(
            {
                "subtotal": state.subtotal,
                "discount": discount,
                "rule": rule,
            }
        )

    def calculate_final_total(
        self, order_id: str, subtotal: float, discount: float, tax_rate: float = 0.18
    ) -> str:
        """Deterministically compute sample tax (18% default) and final payable amount."""
        state = self.get_state(order_id)
        auth_subtotal = state.subtotal if state.subtotal > 0 else state.estimated_order_value
        auth_discount = state.discount
        effective_tax_rate = self.config.tax_rate

        taxable = max(0.0, round(auth_subtotal - auth_discount, 2))
        tax = round(taxable * effective_tax_rate, 2)
        final_total = round(taxable + tax, 2)

        state.subtotal = round(auth_subtotal, 2)
        state.discount = round(auth_discount, 2)
        state.tax = tax
        state.final_total = final_total
        state.pricing_status = "PRICED"

        msg = (
            f"Final total computed (demo {int(effective_tax_rate * 100)}% tax): "
            f"Subtotal INR {state.subtotal:.2f} - Discount INR {state.discount:.2f} "
            f"+ Tax INR {state.tax:.2f} = INR {state.final_total:.2f}."
        )
        self._record(
            state, "Pricing Agent", "calculate_total", "calculate_final_total", "PRICED", msg
        )
        return json.dumps(
            {
                "subtotal": state.subtotal,
                "discount": state.discount,
                "tax_rate": effective_tax_rate,
                "tax": state.tax,
                "final_total": state.final_total,
                "pricing_status": "PRICED",
            }
        )

    # =====================================================================
    # AGENT 5: DISPATCH COORDINATOR TOOLS
    # =====================================================================

    def select_shipping_method(self, order_id: str, address: str) -> str:
        """Select shipping method and compute deterministic expected delivery date & ETA window."""
        state = self.get_state(order_id)
        addr_lower = (state.address or address or "").lower()
        now = datetime.now(timezone.utc)

        if any(city in addr_lower for city in self.METRO_CITIES):
            method = "Express Metro Courier (1-2 Business Days)"
            eta_dt = now + timedelta(days=2)
            eta_window = f"1-2 Business Days (Expected by {eta_dt.strftime('%d %b %Y')})"
        else:
            method = "Standard National Courier (3-5 Business Days)"
            eta_dt = now + timedelta(days=5)
            eta_window = f"3-5 Business Days (Expected by {eta_dt.strftime('%d %b %Y')})"

        state.shipping_method = method
        state.expected_delivery_date = eta_dt.strftime("%Y-%m-%d")
        state.delivery_eta_window = eta_window
        msg = f"Selected shipping method: {method}. {eta_window}."
        self._record(
            state, "Dispatch Coordinator", "select_shipping", "select_shipping_method", "SELECTED", msg
        )
        return json.dumps(
            {
                "order_id": state.order_id,
                "shipping_method": method,
                "expected_delivery_date": state.expected_delivery_date,
                "delivery_eta_window": eta_window,
            }
        )

    def generate_tracking_id(self, order_id: str) -> str:
        """Generate a deterministic, unique-looking tracking ID for the order."""
        state = self.get_state(order_id)
        if not state.tracking_id:
            digest = hashlib.sha256(f"{state.order_id}:{state.customer_id}".encode("utf-8")).hexdigest()[:8].upper()
            state.tracking_id = f"TRK-{digest}"

        msg = f"Generated shipment tracking ID: {state.tracking_id}."
        self._record(
            state,
            "Dispatch Coordinator",
            "generate_tracking",
            "generate_tracking_id",
            "GENERATED",
            msg,
        )
        return json.dumps({"order_id": state.order_id, "tracking_id": state.tracking_id})

    def confirm_dispatch(self, order_id: str) -> str:
        """Confirm dispatch ONLY if every mandatory upstream check passed."""
        state = self.get_state(order_id)

        # Hard programmatic guardrail: NEVER dispatch an invalid, shortfall, or high-fraud order
        blockers: list[str] = []
        if state.validation_status != "VALID":
            blockers.append(f"validation_status={state.validation_status}")
        if state.inventory_status != "RESERVED":
            blockers.append(f"inventory_status={state.inventory_status}")
        if state.fraud_status not in {"LOW", "MEDIUM"}:
            blockers.append(f"fraud_status={state.fraud_status}")
        if state.fraud_status == "MEDIUM" and self.config.hold_on_medium_risk:
            blockers.append("hold_on_medium_risk=True")
        if state.pricing_status != "PRICED":
            blockers.append(f"pricing_status={state.pricing_status}")

        if blockers:
            state.dispatch_status = "HELD"
            state.decision = "HELD_FOR_REVIEW"
            state.hold_reason = "Dispatch blocked by safety guardrail: " + ", ".join(blockers)
            self._record(
                state,
                "Dispatch Coordinator",
                "confirm_dispatch",
                "confirm_dispatch",
                "BLOCKED",
                state.hold_reason,
            )
            return json.dumps({"dispatched": False, "decision": state.decision, "reason": state.hold_reason})

        if not state.shipping_method:
            self.select_shipping_method(state.order_id, state.address)
        if not state.tracking_id:
            self.generate_tracking_id(state.order_id)

        state.dispatch_status = "DISPATCHED"
        state.decision = "DISPATCHED"
        eta_text = f", ETA: {state.delivery_eta_window}" if state.delivery_eta_window else ""
        msg = (
            f"Order {state.order_id} confirmed and DISPATCHED via {state.shipping_method} "
            f"(Tracking ID: {state.tracking_id}{eta_text}, Final Total: INR {state.final_total:.2f})."
        )
        self._record(
            state, "Dispatch Coordinator", "confirm_dispatch", "confirm_dispatch", "DISPATCHED", msg
        )
        return json.dumps(
            {
                "dispatched": True,
                "decision": "DISPATCHED",
                "shipping_method": state.shipping_method,
                "tracking_id": state.tracking_id,
                "expected_delivery_date": state.expected_delivery_date,
                "delivery_eta_window": state.delivery_eta_window,
                "final_total": state.final_total,
            }
        )
