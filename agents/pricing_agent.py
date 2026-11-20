"""Agent 4: Pricing Agent built with Microsoft Agent Framework."""

from __future__ import annotations

import asyncio
from typing import Optional

from agent_framework import Agent, tool
from agent_framework.ollama import OllamaChatClient

from agents import clean_agent_text
from core.order_state import OrderState
from tools.business_tools import BusinessToolkit

AGENT_NAME = "Pricing Agent"
AGENT_ROLE = "Deterministically calculates subtotal, configurable discount, sample tax, and final payable amount."
AGENT_TOOLS = ["get_product_price", "calculate_discount", "calculate_final_total"]

INSTRUCTIONS = (
    "You are the Pricing Agent in an e-commerce order fulfilment pipeline. "
    "Never invent financial numbers. Always call all three tools in order: "
    "1) get_product_price(order_id, product_id), "
    "2) calculate_discount(order_id, subtotal), "
    "3) calculate_final_total(order_id, subtotal, discount, tax_rate). "
    "Return a concise 1-2 sentence summary citing the exact tool-computed figures."
)


def build_pricing_agent(client: OllamaChatClient, toolkit: BusinessToolkit) -> Agent:
    """Create a Microsoft Agent Framework Pricing Agent with registered Python tools."""

    @tool(
        name="get_product_price",
        description="Look up authoritative product unit price and compute order subtotal.",
    )
    def get_product_price(order_id: str, product_id: str) -> str:
        return toolkit.get_product_price(order_id=order_id, product_id=product_id)

    @tool(
        name="calculate_discount",
        description="Compute configurable demonstration discount (5% if subtotal >= INR 3,000).",
    )
    def calculate_discount(order_id: str, subtotal: float) -> str:
        return toolkit.calculate_discount(order_id=order_id, subtotal=subtotal)

    @tool(
        name="calculate_final_total",
        description="Compute configurable sample tax (18%) and final payable total.",
    )
    def calculate_final_total(
        order_id: str, subtotal: float, discount: float, tax_rate: float = 0.18
    ) -> str:
        return toolkit.calculate_final_total(
            order_id=order_id, subtotal=subtotal, discount=discount, tax_rate=tax_rate
        )

    return Agent(
        client=client,
        name=AGENT_NAME,
        description=AGENT_ROLE,
        instructions=INSTRUCTIONS,
        tools=[get_product_price, calculate_discount, calculate_final_total],
        default_options={"think": False, "temperature": 0.0, "num_ctx": 2048, "num_predict": 512, "keep_alive": "10m"},
    )


def run_pricing_deterministic(state: OrderState, toolkit: BusinessToolkit) -> str:
    """Execute 100% deterministic pricing calculations."""
    pid = state.primary_item.get("product_id", "")
    toolkit.get_product_price(state.order_id, pid)
    toolkit.calculate_discount(state.order_id, state.subtotal)
    toolkit.calculate_final_total(
        state.order_id, state.subtotal, state.discount, toolkit.config.tax_rate
    )

    summary = (
        f"PRICED: Subtotal INR {state.subtotal:,.2f} - Discount INR {state.discount:,.2f} "
        f"+ Tax ({int(toolkit.config.tax_rate * 100)}%) INR {state.tax:,.2f} "
        f"= Final Total INR {state.final_total:,.2f}."
    )
    state.agent_summaries[AGENT_NAME] = summary
    return summary


async def run_pricing_agent(
    state: OrderState,
    toolkit: BusinessToolkit,
    client: Optional[OllamaChatClient] = None,
    mode: str = "OLLAMA",
    timeout_seconds: float = 45.0,
) -> str:
    """Run Pricing Agent via Microsoft Agent Framework + Ollama or deterministic DEMO mode."""
    if mode.upper() != "OLLAMA" or client is None:
        return run_pricing_deterministic(state, toolkit)

    pid = state.primary_item.get("product_id", "")
    agent = build_pricing_agent(client, toolkit)
    prompt = (
        f"Calculate deterministic pricing for order {state.order_id}.\n"
        f"- product_id: {pid}\n"
        f"- tax_rate: {toolkit.config.tax_rate}\n"
        "Call get_product_price, calculate_discount, and calculate_final_total now."
    )

    response = await asyncio.wait_for(agent.run(prompt), timeout=timeout_seconds)
    text = clean_agent_text(response.text)

    # Guarantee every deterministic pricing step ran
    called_tools = {t["tool_used"] for t in state.execution_trace if t["agent_name"] == AGENT_NAME}
    if "get_product_price" not in called_tools:
        toolkit.get_product_price(state.order_id, pid)
    if "calculate_discount" not in called_tools:
        toolkit.calculate_discount(state.order_id, state.subtotal)
    if "calculate_final_total" not in called_tools or state.pricing_status != "PRICED":
        toolkit.calculate_final_total(
            state.order_id, state.subtotal, state.discount, toolkit.config.tax_rate
        )

    summary = text or (
        f"PRICED: Final Total INR {state.final_total:,.2f} "
        f"(Subtotal INR {state.subtotal:,.2f}, Discount INR {state.discount:,.2f}, Tax INR {state.tax:,.2f})."
    )
    state.agent_summaries[AGENT_NAME] = summary
    return summary
