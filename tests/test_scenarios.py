"""Automated pytest scenarios for CSE476 E-Commerce Order Fulfilment Orchestrator.

Runs against isolated temporary SQLite databases and JSONL logs so the main demo DB
is never touched, and runs deterministically without requiring a live LLM connection.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.orchestrator import OrderFulfilmentOrchestrator

PRODUCTS_JSON = PROJECT_ROOT / "data" / "products.json"


@pytest.fixture()
def orchestrator(tmp_path: Path) -> OrderFulfilmentOrchestrator:
    """Create an isolated orchestrator backed by a temporary SQLite DB and JSONL log."""
    return OrderFulfilmentOrchestrator(
        db_path=tmp_path / "test_orders.db",
        products_json_path=PRODUCTS_JSON,
        log_path=tmp_path / "test_execution.jsonl",
    )


def test_1_successful_order_dispatched(orchestrator: OrderFulfilmentOrchestrator) -> None:
    """TEST 1: Valid paid order with stock and low risk -> DISPATCHED with deterministic pricing."""
    before_stock = orchestrator.db.get_product("P102")["stock"]

    state = orchestrator.process_order(
        customer_id="C102",
        customer_name="Priya Nair",
        product_id="P102",
        quantity=1,
        address="18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
        payment_status="PAID",
        mode="DEMO",
    )

    assert state.decision == "DISPATCHED"
    assert state.validation_status == "VALID"
    assert state.inventory_status == "RESERVED"
    assert state.fraud_status == "LOW"
    assert state.pricing_status == "PRICED"
    assert state.dispatch_status == "DISPATCHED"
    assert state.tracking_id is not None and state.tracking_id.startswith("TRK-")
    assert state.shipping_method is not None and "Express Metro" in state.shipping_method

    # Deterministic pricing verification: 3500 - 5% (175) = 3325; +18% tax (598.50) = 3923.50
    assert state.subtotal == 3500.0
    assert state.discount == 175.0
    assert state.tax == 598.5
    assert state.final_total == 3923.5

    # Stock decremented by exactly 1
    assert orchestrator.db.get_product("P102")["stock"] == before_stock - 1

    # Append-only JSONL log populated
    logs = orchestrator.logger.read_all(order_id=state.order_id)
    assert len(logs) >= 10


def test_2_stock_shortage_no_dispatch(orchestrator: OrderFulfilmentOrchestrator) -> None:
    """TEST 2: Out-of-stock product (P104) -> SHORTFALL, substitute suggested, never dispatched."""
    state = orchestrator.process_order(
        customer_id="C101",
        customer_name="Aarav Sharma",
        product_id="P104",
        quantity=1,
        address="42 MG Road, Bengaluru, Karnataka 560001",
        payment_status="PAID",
        mode="DEMO",
    )

    assert state.validation_status == "VALID"
    assert state.inventory_status == "SHORTFALL"
    assert state.decision == "SHORTFALL"
    assert state.dispatch_status == "NOT_DISPATCHED"
    assert state.tracking_id is None
    assert state.substitute_suggestion is not None
    assert state.substitute_suggestion["product_id"] == "P105"
    # Stock must never become negative
    assert orchestrator.db.get_product("P104")["stock"] == 0


def test_3_payment_failure_rejected(orchestrator: OrderFulfilmentOrchestrator) -> None:
    """TEST 3: Unpaid order -> REJECTED at Validation stage; no stock reserved and no dispatch."""
    before_stock = orchestrator.db.get_product("P101")["stock"]

    state = orchestrator.process_order(
        customer_id="C101",
        customer_name="Aarav Sharma",
        product_id="P101",
        quantity=2,
        address="42 MG Road, Bengaluru, Karnataka 560001",
        payment_status="UNPAID",
        mode="DEMO",
    )

    assert state.validation_status == "INVALID"
    assert state.decision == "REJECTED"
    assert state.inventory_status == "PENDING"
    assert state.dispatch_status == "NOT_DISPATCHED"
    assert state.tracking_id is None
    assert orchestrator.db.get_product("P101")["stock"] == before_stock


def test_4_high_fraud_risk_held(orchestrator: OrderFulfilmentOrchestrator) -> None:
    """TEST 4: Customer with suspicious prior history (C104) -> HELD_FOR_REVIEW and no dispatch."""
    state = orchestrator.process_order(
        customer_id="C104",
        customer_name="Vikram Mehta",
        product_id="P101",
        quantity=1,
        address="901 Linking Road, Mumbai, Maharashtra 400050",
        payment_status="PAID",
        mode="DEMO",
    )

    assert state.validation_status == "VALID"
    assert state.inventory_status == "RESERVED"
    assert state.fraud_status == "HIGH"
    assert state.fraud_score >= 60
    assert state.decision == "HELD_FOR_REVIEW"
    assert state.dispatch_status == "HELD"
    assert state.tracking_id is None
    assert state.hold_reason is not None and "Fraud escalation" in state.hold_reason

    # Verify fraud flag was persisted in SQLite
    details = orchestrator.db.get_order_details(state.order_id)
    assert details is not None
    assert len(details["fraud_flags"]) >= 1


def test_5_repeat_customer_memory_persists_across_restarts(tmp_path: Path) -> None:
    """TEST 5: SQLite prior-order memory survives restart and updates repeat customer fraud score."""
    db_file = tmp_path / "persist_orders.db"
    log_file = tmp_path / "persist_exec.jsonl"

    # Run 1: Brand-new customer C999 places a high-value order (>= 5000) -> +25 +15 = 40 (MEDIUM)
    # Fraud flag gets persisted in SQLite.
    orch1 = OrderFulfilmentOrchestrator(
        db_path=db_file, products_json_path=PRODUCTS_JSON, log_path=log_file
    )
    first_order = orch1.process_order(
        customer_id="C999",
        customer_name="Neha Kapoor",
        product_id="P102",
        quantity=2,  # 7,000 INR >= 5,000
        address="10 Park Street, Kolkata, West Bengal 700016",
        payment_status="PAID",
        mode="DEMO",
    )
    assert first_order.fraud_score == 40
    assert first_order.fraud_status == "MEDIUM"
    assert first_order.decision == "DISPATCHED"

    # Simulate application restart with a fresh orchestrator pointing to the same SQLite DB
    orch2 = OrderFulfilmentOrchestrator(
        db_path=db_file, products_json_path=PRODUCTS_JSON, log_path=log_file
    )
    second_order = orch2.process_order(
        customer_id="C999",
        customer_name="Neha Kapoor",
        product_id="P105",
        quantity=1,  # 1,200 INR (low value), but C999 now has 1 prior order + 1 prior fraud flag (+30)
        address="10 Park Street, Kolkata, West Bengal 700016",
        payment_status="PAID",
        mode="DEMO",
    )
    assert second_order.customer_history_summary["total_prior_orders"] == 1
    assert second_order.customer_history_summary["prior_fraud_flags"] == 1
    assert second_order.fraud_score == 30  # Reflects persisted SQLite fraud flag!
    assert second_order.fraud_status == "MEDIUM"

    # Append-only log must contain BOTH orders
    raw_lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    logged_order_ids = {entry["order_id"] for entry in raw_lines}
    assert first_order.order_id in logged_order_ids
    assert second_order.order_id in logged_order_ids


def test_6_duplicate_submission_prevents_double_deduction(
    orchestrator: OrderFulfilmentOrchestrator,
) -> None:
    """TEST 6: Duplicate idempotency_key returns existing order without deducting stock twice."""
    before_stock = orchestrator.db.get_product("P105")["stock"]
    key = "submit-token-abc-123"

    first = orchestrator.process_order(
        customer_id="C101",
        customer_name="Aarav Sharma",
        product_id="P105",
        quantity=2,
        address="42 MG Road, Bengaluru, Karnataka 560001",
        payment_status="PAID",
        idempotency_key=key,
        mode="DEMO",
    )
    after_first_stock = orchestrator.db.get_product("P105")["stock"]

    second = orchestrator.process_order(
        customer_id="C101",
        customer_name="Aarav Sharma",
        product_id="P105",
        quantity=2,
        address="42 MG Road, Bengaluru, Karnataka 560001",
        payment_status="PAID",
        idempotency_key=key,
        mode="DEMO",
    )
    after_second_stock = orchestrator.db.get_product("P105")["stock"]

    assert first.decision == "DISPATCHED"
    assert second.order_id == first.order_id
    assert after_first_stock == before_stock - 2
    assert after_second_stock == after_first_stock


def test_7_invalid_inputs_and_dispatch_guardrail(orchestrator: OrderFulfilmentOrchestrator) -> None:
    """TEST 7: Invalid product, missing address, invalid qty rejected; dispatch guardrail blocks unsafe state."""
    bad = orchestrator.process_order(
        customer_id="C101",
        customer_name="Aarav Sharma",
        product_id="P999",
        quantity=0,
        address="short",
        payment_status="PAID",
        mode="DEMO",
    )
    assert bad.decision == "REJECTED"
    assert bad.validation_status == "INVALID"
    assert len(bad.validation_reasons) >= 2

    # Even if confirm_dispatch is called directly on the rejected order, safety guardrail blocks it
    result = json.loads(orchestrator.toolkit.confirm_dispatch(bad.order_id))
    assert result["dispatched"] is False
    assert bad.dispatch_status == "HELD"


def test_8_storefront_to_admin_flow_eta_spam_and_restock(
    orchestrator: OrderFulfilmentOrchestrator,
) -> None:
    """TEST 8: Storefront checkout -> Admin 5-agent verification with ETA, anti-spam check, and fraud-reject restock."""
    # 1. Customer submits order via storefront -> queued as PENDING_REVIEW without deducting stock
    before_stock = orchestrator.db.get_product("P101")["stock"]
    pending = orchestrator.submit_customer_order(
        customer_id="C102",
        customer_name="Priya Nair",
        customer_phone="+91 98801 44556",
        product_id="P101",
        quantity=1,
        address="18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
        payment_status="PAID",
    )
    assert pending.decision == "PENDING_REVIEW"
    assert orchestrator.db.get_product("P101")["stock"] == before_stock

    # 2. Admin runs 5-agent verification on the pending order -> DISPATCHED with Tracking ID + Expected Delivery Date
    verified = orchestrator.process_pending_order(pending.order_id, mode="DEMO")
    assert verified.order_id == pending.order_id
    assert verified.decision == "DISPATCHED"
    assert verified.tracking_id is not None
    assert verified.expected_delivery_date is not None
    assert verified.delivery_eta_window is not None
    assert orchestrator.db.get_product("P101")["stock"] == before_stock - 1

    # 3. Spam / invalid phone rejected by Validation Agent
    spam = orchestrator.process_order(
        customer_id="C105",
        customer_name="Fake Spam Buyer",
        customer_phone="1111111111",
        product_id="P101",
        quantity=1,
        address="aaaaaaa fake street",
        payment_status="PAID",
        mode="DEMO",
    )
    assert spam.decision == "REJECTED"
    assert spam.validation_status == "INVALID"

    # 4. Fraud-held order rejected by Admin automatically releases reserved stock back to inventory
    stock_before_fraud = orchestrator.db.get_product("P105")["stock"]
    held = orchestrator.process_order(
        customer_id="C104",
        customer_name="Vikram Mehta",
        customer_phone="+91 98200 99001",
        product_id="P105",
        quantity=2,
        address="901 Linking Road, Mumbai, Maharashtra 400050",
        payment_status="PAID",
        mode="DEMO",
    )
    assert held.decision == "HELD_FOR_REVIEW"
    assert orchestrator.db.get_product("P105")["stock"] == stock_before_fraud - 2

    rejected = orchestrator.admin_resolve_held_order(held.order_id, "REJECT", "Confirmed fraud")
    assert rejected.decision == "REJECTED"
    assert orchestrator.db.get_product("P105")["stock"] == stock_before_fraud

