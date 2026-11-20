"""Agent 3: Fraud Check Agent built with Microsoft Agent Framework."""

from __future__ import annotations

import asyncio
from typing import Optional

from agent_framework import Agent, tool
from agent_framework.ollama import OllamaChatClient

from agents import clean_agent_text
from core.order_state import OrderState
from tools.business_tools import BusinessToolkit

AGENT_NAME = "Fraud Check Agent"
AGENT_ROLE = "Queries SQLite customer history, computes a transparent risk score, and escalates high-risk orders."
AGENT_TOOLS = ["get_customer_history", "calculate_fraud_score", "record_fraud_flag"]

INSTRUCTIONS = (
    "You are the Fraud Check Agent in an e-commerce order fulfilment pipeline. "
    "Step 1: Call get_customer_history(order_id, customer_id). "
    "Step 2: Call calculate_fraud_score(order_id, customer_id). "
    "Step 3: If risk_level is MEDIUM or HIGH, call record_fraud_flag(order_id, customer_id, reason). "
    "Respond in 1-2 concise sentences summarizing the risk level (LOW/MEDIUM/HIGH), score, and key reasons."
)


def build_fraud_agent(client: OllamaChatClient, toolkit: BusinessToolkit) -> Agent:
    """Create a Microsoft Agent Framework Fraud Check Agent with registered Python tools."""

    @tool(
        name="get_customer_history",
        description="Retrieve customer prior orders, failed payments, cancellations, and fraud flags from SQLite.",
    )
    def get_customer_history(order_id: str, customer_id: str) -> str:
        return toolkit.get_customer_history(order_id=order_id, customer_id=customer_id)

    @tool(
        name="calculate_fraud_score",
        description="Compute deterministic fraud risk score (0-100) and risk level (LOW/MEDIUM/HIGH).",
    )
    def calculate_fraud_score(order_id: str, customer_id: str) -> str:
        return toolkit.calculate_fraud_score(order_id=order_id, customer_id=customer_id)

    @tool(
        name="record_fraud_flag",
        description="Persist a fraud flag in SQLite for MEDIUM or HIGH risk orders.",
    )
    def record_fraud_flag(order_id: str, customer_id: str, reason: str) -> str:
        return toolkit.record_fraud_flag(order_id=order_id, customer_id=customer_id, reason=reason)

    return Agent(
        client=client,
        name=AGENT_NAME,
        description=AGENT_ROLE,
        instructions=INSTRUCTIONS,
        tools=[get_customer_history, calculate_fraud_score, record_fraud_flag],
        default_options={"think": False, "temperature": 0.0, "num_ctx": 2048, "num_predict": 512, "keep_alive": "10m"},
    )


def run_fraud_deterministic(state: OrderState, toolkit: BusinessToolkit) -> str:
    """Execute deterministic SQLite history lookup, fraud scoring, and flagging."""
    toolkit.get_customer_history(state.order_id, state.customer_id)
    toolkit.calculate_fraud_score(state.order_id, state.customer_id)

    if state.fraud_status in {"MEDIUM", "HIGH"}:
        reason = "; ".join(state.fraud_reasons) or f"Fraud risk score {state.fraud_score}/100"
        toolkit.record_fraud_flag(state.order_id, state.customer_id, reason)

    reasons_text = "; ".join(state.fraud_reasons) if state.fraud_reasons else "Clean customer history."
    summary = f"{state.fraud_status} RISK (Score {state.fraud_score}/100): {reasons_text}"
    state.agent_summaries[AGENT_NAME] = summary
    return summary


async def run_fraud_agent(
    state: OrderState,
    toolkit: BusinessToolkit,
    client: Optional[OllamaChatClient] = None,
    mode: str = "OLLAMA",
    timeout_seconds: float = 45.0,
) -> str:
    """Run Fraud Check Agent via Microsoft Agent Framework + Ollama or deterministic DEMO mode."""
    if mode.upper() != "OLLAMA" or client is None:
        return run_fraud_deterministic(state, toolkit)

    agent = build_fraud_agent(client, toolkit)
    prompt = (
        f"Assess fraud risk for order {state.order_id}.\n"
        f"- customer_id: {state.customer_id}\n"
        f"- estimated_value_inr: {state.estimated_order_value:.2f}\n"
        "Call get_customer_history, then calculate_fraud_score, and call record_fraud_flag if risk is MEDIUM or HIGH."
    )

    response = await asyncio.wait_for(agent.run(prompt), timeout=timeout_seconds)
    text = clean_agent_text(response.text)

    # Guarantee deterministic memory retrieval, scoring, and flag persistence
    called_tools = {t["tool_used"] for t in state.execution_trace if t["agent_name"] == AGENT_NAME}
    if "get_customer_history" not in called_tools:
        toolkit.get_customer_history(state.order_id, state.customer_id)
    if "calculate_fraud_score" not in called_tools or state.fraud_status == "PENDING":
        toolkit.calculate_fraud_score(state.order_id, state.customer_id)
    if state.fraud_status in {"MEDIUM", "HIGH"} and "record_fraud_flag" not in called_tools:
        reason = "; ".join(state.fraud_reasons) or f"Fraud risk score {state.fraud_score}/100"
        toolkit.record_fraud_flag(state.order_id, state.customer_id, reason)

    summary = text or f"{state.fraud_status} RISK (Score {state.fraud_score}/100)."
    state.agent_summaries[AGENT_NAME] = summary
    return summary
