"""CLI entrypoint to run sample end-to-end order fulfilment scenarios."""

from __future__ import annotations

import argparse

from core.orchestrator import OrderFulfilmentOrchestrator


def print_result(title: str, state) -> None:
    print("=" * 72)
    print(f"SCENARIO: {title}")
    print(f"Order ID: {state.order_id} | Customer: {state.customer_id} ({state.customer_name})")
    print(f"Mode: {state.execution_mode} | Final Decision: {state.decision}")
    print(
        f"Stages -> Validation: {state.validation_status} | Inventory: {state.inventory_status} | "
        f"Fraud: {state.fraud_status} ({state.fraud_score}/100) | Pricing: {state.pricing_status} | "
        f"Dispatch: {state.dispatch_status}"
    )
    if state.decision == "DISPATCHED":
        print(
            f"Pricing -> Subtotal: INR {state.subtotal:,.2f} | Discount: INR {state.discount:,.2f} | "
            f"Tax: INR {state.tax:,.2f} | Final Total: INR {state.final_total:,.2f}"
        )
        print(f"Shipping -> {state.shipping_method} | Tracking ID: {state.tracking_id}")
    elif state.hold_reason:
        print(f"Reason -> {state.hold_reason}")
    print(f"Trace Events Logged: {len(state.execution_trace)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CSE476 E-Commerce Order Fulfilment Orchestrator CLI")
    parser.add_argument(
        "--mode",
        choices=["OLLAMA", "DEMO"],
        default="OLLAMA",
        help="Execution mode: OLLAMA (live Microsoft Agent Framework + Ollama) or DEMO (deterministic).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset demo SQLite database before running sample scenarios.",
    )
    args = parser.parse_args()

    orch = OrderFulfilmentOrchestrator()
    if args.reset:
        orch.db.reset_demo_data()

    ok, msg = orch.ollama_status()
    print(f"Ollama Health: {msg}")

    s1 = orch.process_order(
        customer_id="C102",
        customer_name="Priya Nair",
        product_id="P102",
        quantity=1,
        address="18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
        payment_status="PAID",
        mode=args.mode,
    )
    print_result("Successful Trusted Repeat Customer Order", s1)

    s2 = orch.process_order(
        customer_id="C104",
        customer_name="Vikram Mehta",
        product_id="P101",
        quantity=1,
        address="901 Linking Road, Mumbai, Maharashtra 400050",
        payment_status="PAID",
        mode=args.mode,
    )
    print_result("High Fraud Risk Escalation (Prior History in SQLite)", s2)

    s3 = orch.process_order(
        customer_id="C101",
        customer_name="Aarav Sharma",
        product_id="P104",
        quantity=1,
        address="42 MG Road, Bengaluru, Karnataka 560001",
        payment_status="PAID",
        mode=args.mode,
    )
    print_result("Out-of-Stock Shortfall with Substitute", s3)


if __name__ == "__main__":
    main()
