"""Shared OrderState data model and append-only JSONL execution logger."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class OrderState:
    """Central shared order-state object passed and updated across all five agents."""

    order_id: str
    customer_id: str
    customer_name: str = ""
    customer_phone: str = ""
    items: list[dict[str, Any]] = field(default_factory=list)
    address: str = ""
    payment_status: str = "UNPAID"

    # Per-agent stage statuses
    validation_status: str = "PENDING"
    inventory_status: str = "PENDING"
    fraud_status: str = "PENDING"
    pricing_status: str = "PENDING"
    dispatch_status: str = "PENDING"

    # Detailed stage outcomes
    validation_reasons: list[str] = field(default_factory=list)
    substitute_suggestion: Optional[dict[str, Any]] = None
    fraud_score: int = 0
    fraud_reasons: list[str] = field(default_factory=list)
    customer_history_summary: dict[str, Any] = field(default_factory=dict)

    # Deterministic financial fields (INR)
    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    final_total: float = 0.0

    # Dispatch fields
    tracking_id: Optional[str] = None
    shipping_method: Optional[str] = None
    expected_delivery_date: Optional[str] = None
    delivery_eta_window: Optional[str] = None

    # Final pipeline decision
    decision: str = "PENDING"
    hold_reason: Optional[str] = None

    # Execution metadata & trace
    execution_mode: str = "DEMO"
    idempotency_key: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    agent_summaries: dict[str, str] = field(default_factory=dict)
    execution_trace: list[dict[str, Any]] = field(default_factory=list)

    @property
    def primary_item(self) -> dict[str, Any]:
        """Return the primary item dict (empty dict if no items)."""
        return self.items[0] if self.items else {}

    @property
    def estimated_order_value(self) -> float:
        """Compute deterministic gross item value from items."""
        total = 0.0
        for item in self.items:
            qty = int(item.get("quantity", 0))
            price = float(item.get("unit_price", 0.0))
            total += qty * price
        return round(total, 2)

    def add_trace(
        self,
        agent_name: str,
        action: str,
        tool_used: str,
        result: str,
        explanation: str,
    ) -> dict[str, Any]:
        """Record an event in the in-memory execution trace and return the entry."""
        entry = {
            "timestamp": utc_now_iso(),
            "order_id": self.order_id,
            "agent_name": agent_name,
            "action": action,
            "tool_used": tool_used,
            "result": result,
            "explanation": explanation,
            "execution_mode": self.execution_mode,
        }
        self.execution_trace.append(entry)
        return entry

    def to_dict(self) -> dict[str, Any]:
        """Serialize the state to a plain dictionary."""
        return asdict(self)


class ExecutionLogger:
    """Append-only JSON Lines execution logger (never overwrites prior records)."""

    def __init__(self, log_path: Path | str) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()

    def append(self, entry: dict[str, Any]) -> None:
        """Append a single execution event as one JSON line."""
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_all(self, order_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Read logged events, optionally filtered by order_id."""
        if not self.log_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with self.log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if order_id is None or record.get("order_id") == order_id:
                    entries.append(record)
        return entries
