"""Agent 2: Inventory Agent built with Microsoft Agent Framework."""

from __future__ import annotations

import asyncio
from typing import Optional

from agent_framework import Agent, tool
from agent_framework.ollama import OllamaChatClient

from agents import clean_agent_text
from core.order_state import OrderState
from tools.business_tools import BusinessToolkit

AGENT_NAME = "Inventory Agent"
AGENT_ROLE = "Checks stock levels, atomically reserves inventory, and suggests substitutes on shortfall."
AGENT_TOOLS = ["get_stock_level", "reserve_stock", "suggest_substitute"]

INSTRUCTIONS = (
    "You are the Inventory Agent in an e-commerce order fulfilment pipeline. "
    "Step 1: Call get_stock_level(order_id, product_id). "
    "Step 2: If sufficient stock is available, call reserve_stock(order_id, product_id, quantity). "
    "Step 3: If stock is insufficient, call suggest_substitute(order_id, product_id). "
    "Respond in 1-2 concise sentences stating RESERVED or SHORTFALL and any substitute."
)


def build_inventory_agent(client: OllamaChatClient, toolkit: BusinessToolkit) -> Agent:
    """Create a Microsoft Agent Framework Inventory Agent with registered Python tools."""

    @tool(
        name="get_stock_level",
        description="Check current available stock for product_id.",
    )
    def get_stock_level(order_id: str, product_id: str) -> str:
        return toolkit.get_stock_level(order_id=order_id, product_id=product_id)

    @tool(
        name="reserve_stock",
        description="Reserve requested quantity of product_id atomically (prevents negative stock).",
    )
    def reserve_stock(order_id: str, product_id: str, quantity: int) -> str:
        return toolkit.reserve_stock(order_id=order_id, product_id=product_id, quantity=quantity)

    @tool(
        name="suggest_substitute",
        description="Suggest an in-stock substitute product when requested item is unavailable.",
    )
    def suggest_substitute(order_id: str, product_id: str) -> str:
        return toolkit.suggest_substitute(order_id=order_id, product_id=product_id)

    return Agent(
        client=client,
        name=AGENT_NAME,
        description=AGENT_ROLE,
        instructions=INSTRUCTIONS,
        tools=[get_stock_level, reserve_stock, suggest_substitute],
        default_options={"think": False, "temperature": 0.0, "num_ctx": 2048, "num_predict": 512, "keep_alive": "10m"},
    )


def run_inventory_deterministic(state: OrderState, toolkit: BusinessToolkit) -> str:
    """Execute deterministic inventory check, reservation, or substitute suggestion."""
    pid = state.primary_item.get("product_id", "")
    qty = int(state.primary_item.get("quantity", 0))

    toolkit.get_stock_level(state.order_id, pid)
    toolkit.reserve_stock(state.order_id, pid, qty)

    if state.inventory_status == "RESERVED":
        summary = f"RESERVED: Allocated {qty} unit(s) of {pid}."
    else:
        toolkit.suggest_substitute(state.order_id, pid)
        if state.substitute_suggestion:
            sub = state.substitute_suggestion
            summary = (
                f"SHORTFALL: Insufficient stock for {pid}. "
                f"Suggested substitute: {sub['product_id']} ({sub['name']} - INR {sub['price']:.2f})."
            )
        else:
            summary = f"SHORTFALL: Insufficient stock for {pid}; no substitute available."

    state.agent_summaries[AGENT_NAME] = summary
    return summary


async def run_inventory_agent(
    state: OrderState,
    toolkit: BusinessToolkit,
    client: Optional[OllamaChatClient] = None,
    mode: str = "OLLAMA",
    timeout_seconds: float = 45.0,
) -> str:
    """Run Inventory Agent via Microsoft Agent Framework + Ollama or deterministic DEMO mode."""
    if mode.upper() != "OLLAMA" or client is None:
        return run_inventory_deterministic(state, toolkit)

    pid = state.primary_item.get("product_id", "")
    qty = int(state.primary_item.get("quantity", 0))
    agent = build_inventory_agent(client, toolkit)
    prompt = (
        f"Process inventory for order {state.order_id}.\n"
        f"- product_id: {pid}\n"
        f"- quantity: {qty}\n"
        "First call get_stock_level. Then call reserve_stock if sufficient, or suggest_substitute if insufficient."
    )

    response = await asyncio.wait_for(agent.run(prompt), timeout=timeout_seconds)
    text = clean_agent_text(response.text)

    # Reconcile mandatory state transition if the 4B model missed a step
    called_tools = {t["tool_used"] for t in state.execution_trace if t["agent_name"] == AGENT_NAME}
    if "get_stock_level" not in called_tools:
        toolkit.get_stock_level(state.order_id, pid)
    if state.inventory_status == "PENDING":
        toolkit.reserve_stock(state.order_id, pid, qty)
    if state.inventory_status == "SHORTFALL" and "suggest_substitute" not in called_tools:
        toolkit.suggest_substitute(state.order_id, pid)

    summary = text or (
        f"RESERVED: {qty} unit(s) of {pid} reserved."
        if state.inventory_status == "RESERVED"
        else f"SHORTFALL: Unable to reserve {qty} unit(s) of {pid}."
    )
    state.agent_summaries[AGENT_NAME] = summary
    return summary
