"""Agent 1: Validation Agent built with Microsoft Agent Framework."""

from __future__ import annotations

import asyncio
from typing import Optional

from agent_framework import Agent, tool
from agent_framework.ollama import OllamaChatClient

from agents import clean_agent_text
from core.order_state import OrderState
from tools.business_tools import BusinessToolkit

AGENT_NAME = "Validation Agent"
AGENT_ROLE = "Verifies product existence, quantity, delivery address, and payment status."
AGENT_TOOLS = ["check_product_exists", "validate_address", "verify_payment"]

INSTRUCTIONS = (
    "You are the Validation Agent in an e-commerce order fulfilment pipeline. "
    "Always call all three tools in order: check_product_exists, validate_address, and verify_payment "
    "using the exact order_id, product_id, address, and payment_status provided. "
    "After calling all three tools, return a concise 1-2 sentence validation verdict (VALID or INVALID) with reasons."
)


def build_validation_agent(client: OllamaChatClient, toolkit: BusinessToolkit) -> Agent:
    """Create a Microsoft Agent Framework Validation Agent with registered Python tools."""

    @tool(
        name="check_product_exists",
        description="Check if product_id exists in the catalog and quantity is valid.",
    )
    def check_product_exists(order_id: str, product_id: str) -> str:
        return toolkit.check_product_exists(order_id=order_id, product_id=product_id)

    @tool(
        name="validate_address",
        description="Validate that the customer delivery address is complete.",
    )
    def validate_address(order_id: str, address: str) -> str:
        return toolkit.validate_address(order_id=order_id, address=address)

    @tool(
        name="verify_payment",
        description="Verify whether the order payment status is PAID.",
    )
    def verify_payment(order_id: str, payment_status: str) -> str:
        return toolkit.verify_payment(order_id=order_id, payment_status=payment_status)

    return Agent(
        client=client,
        name=AGENT_NAME,
        description=AGENT_ROLE,
        instructions=INSTRUCTIONS,
        tools=[check_product_exists, validate_address, verify_payment],
        default_options={"think": False, "temperature": 0.0, "num_ctx": 2048, "num_predict": 512, "keep_alive": "10m"},
    )


def run_validation_deterministic(state: OrderState, toolkit: BusinessToolkit) -> str:
    """Execute deterministic validation tools (DEMO mode or safeguard completion)."""
    pid = state.primary_item.get("product_id", "")
    toolkit.check_product_exists(state.order_id, pid)
    toolkit.validate_address(state.order_id, state.address)
    toolkit.verify_payment(state.order_id, state.payment_status)

    if state.validation_reasons:
        state.validation_status = "INVALID"
        summary = "INVALID: " + " | ".join(state.validation_reasons)
    else:
        state.validation_status = "VALID"
        summary = f"VALID: Product {pid}, delivery address, and PAID status verified."

    state.agent_summaries[AGENT_NAME] = summary
    return summary


async def run_validation_agent(
    state: OrderState,
    toolkit: BusinessToolkit,
    client: Optional[OllamaChatClient] = None,
    mode: str = "OLLAMA",
    timeout_seconds: float = 45.0,
) -> str:
    """Run Validation Agent via Microsoft Agent Framework + Ollama or deterministic DEMO mode."""
    if mode.upper() != "OLLAMA" or client is None:
        return run_validation_deterministic(state, toolkit)

    pid = state.primary_item.get("product_id", "")
    agent = build_validation_agent(client, toolkit)
    prompt = (
        f"Validate order {state.order_id}.\n"
        f"- product_id: {pid}\n"
        f"- address: {state.address}\n"
        f"- payment_status: {state.payment_status}\n"
        "Call check_product_exists, validate_address, and verify_payment now."
    )

    response = await asyncio.wait_for(agent.run(prompt), timeout=timeout_seconds)
    text = clean_agent_text(response.text)

    # Ensure every mandatory validation check actually ran (4B model safety net)
    called_tools = {t["tool_used"] for t in state.execution_trace if t["agent_name"] == AGENT_NAME}
    if "check_product_exists" not in called_tools:
        toolkit.check_product_exists(state.order_id, pid)
    if "validate_address" not in called_tools:
        toolkit.validate_address(state.order_id, state.address)
    if "verify_payment" not in called_tools:
        toolkit.verify_payment(state.order_id, state.payment_status)

    if state.validation_reasons:
        state.validation_status = "INVALID"
    else:
        state.validation_status = "VALID"

    summary = text or (
        f"VALID: Order {state.order_id} passed all validation checks."
        if state.validation_status == "VALID"
        else "INVALID: " + " | ".join(state.validation_reasons)
    )
    state.agent_summaries[AGENT_NAME] = summary
    return summary
