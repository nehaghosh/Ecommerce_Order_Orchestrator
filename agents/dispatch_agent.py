"""Agent 5: Dispatch Coordinator built with Microsoft Agent Framework."""

from __future__ import annotations

import asyncio
from typing import Optional

from agent_framework import Agent, tool
from agent_framework.ollama import OllamaChatClient

from agents import clean_agent_text
from core.order_state import OrderState
from tools.business_tools import BusinessToolkit

AGENT_NAME = "Dispatch Coordinator"
AGENT_ROLE = "Verifies all upstream stages passed, selects shipping method, generates tracking ID, and confirms dispatch."
AGENT_TOOLS = ["select_shipping_method", "generate_tracking_id", "confirm_dispatch"]

INSTRUCTIONS = (
    "You are the Dispatch Coordinator in an e-commerce order fulfilment pipeline. "
    "Call all three tools in order: "
    "1) select_shipping_method(order_id, address), "
    "2) generate_tracking_id(order_id), "
    "3) confirm_dispatch(order_id). "
    "Return a concise 1-2 sentence dispatch confirmation with shipping method and tracking ID, or explain if held."
)


def build_dispatch_agent(client: OllamaChatClient, toolkit: BusinessToolkit) -> Agent:
    """Create a Microsoft Agent Framework Dispatch Coordinator with registered Python tools."""

    @tool(
        name="select_shipping_method",
        description="Select appropriate shipping method based on customer delivery address.",
    )
    def select_shipping_method(order_id: str, address: str) -> str:
        return toolkit.select_shipping_method(order_id=order_id, address=address)

    @tool(
        name="generate_tracking_id",
        description="Generate a unique tracking ID for the shipment.",
    )
    def generate_tracking_id(order_id: str) -> str:
        return toolkit.generate_tracking_id(order_id=order_id)

    @tool(
        name="confirm_dispatch",
        description="Verify all mandatory upstream stages passed and confirm final dispatch.",
    )
    def confirm_dispatch(order_id: str) -> str:
        return toolkit.confirm_dispatch(order_id=order_id)

    return Agent(
        client=client,
        name=AGENT_NAME,
        description=AGENT_ROLE,
        instructions=INSTRUCTIONS,
        tools=[select_shipping_method, generate_tracking_id, confirm_dispatch],
        default_options={"think": False, "temperature": 0.0, "num_ctx": 2048, "num_predict": 512, "keep_alive": "10m"},
    )


def run_dispatch_deterministic(state: OrderState, toolkit: BusinessToolkit) -> str:
    """Execute deterministic shipping selection, tracking generation, and guarded dispatch."""
    toolkit.select_shipping_method(state.order_id, state.address)
    toolkit.generate_tracking_id(state.order_id)
    toolkit.confirm_dispatch(state.order_id)

    if state.dispatch_status == "DISPATCHED":
        summary = (
            f"DISPATCHED via {state.shipping_method} | Tracking ID: {state.tracking_id}."
        )
    else:
        summary = f"HELD: {state.hold_reason or 'Order failed mandatory dispatch guardrails.'}"

    state.agent_summaries[AGENT_NAME] = summary
    return summary


async def run_dispatch_agent(
    state: OrderState,
    toolkit: BusinessToolkit,
    client: Optional[OllamaChatClient] = None,
    mode: str = "OLLAMA",
    timeout_seconds: float = 45.0,
) -> str:
    """Run Dispatch Coordinator via Microsoft Agent Framework + Ollama or deterministic DEMO mode."""
    if mode.upper() != "OLLAMA" or client is None:
        return run_dispatch_deterministic(state, toolkit)

    agent = build_dispatch_agent(client, toolkit)
    prompt = (
        f"Coordinate dispatch for order {state.order_id}.\n"
        f"- address: {state.address}\n"
        f"- final_total_inr: {state.final_total:.2f}\n"
        "Call select_shipping_method, generate_tracking_id, and confirm_dispatch now."
    )

    response = await asyncio.wait_for(agent.run(prompt), timeout=timeout_seconds)
    text = clean_agent_text(response.text)

    # Ensure mandatory dispatch tools executed
    called_tools = {t["tool_used"] for t in state.execution_trace if t["agent_name"] == AGENT_NAME}
    if "select_shipping_method" not in called_tools:
        toolkit.select_shipping_method(state.order_id, state.address)
    if "generate_tracking_id" not in called_tools:
        toolkit.generate_tracking_id(state.order_id)
    if "confirm_dispatch" not in called_tools or state.dispatch_status == "PENDING":
        toolkit.confirm_dispatch(state.order_id)

    summary = text or (
        f"DISPATCHED via {state.shipping_method} | Tracking ID: {state.tracking_id}."
        if state.dispatch_status == "DISPATCHED"
        else f"HELD: {state.hold_reason}"
    )
    state.agent_summaries[AGENT_NAME] = summary
    return summary
