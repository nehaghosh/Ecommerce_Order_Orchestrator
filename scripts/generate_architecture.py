"""Generate a clean, presentation-ready architecture.png diagram using matplotlib."""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


def draw_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str = "",
    facecolor: str = "#EFF6FF",
    edgecolor: str = "#2563EB",
    title_color: str = "#0F172A",
    fontsize: int = 9,
) -> None:
    box = mpatches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=1.6,
    )
    ax.add_patch(box)
    if subtitle:
        ax.text(
            x + w / 2,
            y + h * 0.66,
            title,
            ha="center",
            va="center",
            fontsize=fontsize,
            fontweight="bold",
            color=title_color,
        )
        ax.text(
            x + w / 2,
            y + h * 0.30,
            subtitle,
            ha="center",
            va="center",
            fontsize=fontsize - 1.5,
            color="#334155",
        )
    else:
        ax.text(
            x + w / 2,
            y + h / 2,
            title,
            ha="center",
            va="center",
            fontsize=fontsize,
            fontweight="bold",
            color=title_color,
        )


def draw_arrow(
    ax, x1: float, y1: float, x2: float, y2: float, color: str = "#334155", label: str = "", lx: float = 0.0, ly: float = 0.0
) -> None:
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.6, mutation_scale=13),
    )
    if label:
        ax.text(
            lx,
            ly,
            label,
            ha="center",
            va="center",
            fontsize=7.6,
            fontweight="bold",
            color=color,
            bbox=dict(facecolor="#F8FAFC", edgecolor="none", pad=1.4),
        )


def main() -> None:
    fig, ax = plt.subplots(figsize=(14, 8), dpi=200)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8.2)
    ax.axis("off")
    fig.patch.set_facecolor("#F8FAFC")

    # Title banner
    ax.text(
        7.0,
        7.85,
        "E-Commerce Order Fulfilment Orchestrator — Multi-Agent Architecture",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color="#0F172A",
    )
    ax.text(
        7.0,
        7.52,
        "CSE476 (Group 11) | Microsoft Agent Framework + Ollama (qwen3:4b) | Pipeline with Fraud Escalation Route",
        ha="center",
        va="center",
        fontsize=9.5,
        color="#475569",
    )

    # Top layer: Customer / Streamlit UI / CLI / Notebook
    draw_box(
        ax,
        0.5,
        6.25,
        3.2,
        0.9,
        "Customer Order Input",
        "Streamlit Ops Dashboard (app.py)\nCLI (main.py) & Demo Notebook",
        facecolor="#0F172A",
        edgecolor="#0F172A",
        title_color="#FFFFFF",
        fontsize=9.5,
    )
    # Override subtitle color on dark box
    for txt in ax.texts[-1:]:
        txt.set_color("#CBD5E1")

    draw_box(
        ax,
        4.6,
        6.25,
        4.6,
        0.9,
        "OrderFulfilmentOrchestrator",
        "core/orchestrator.py | Deterministic Pipeline Gates\nMicrosoft Agent Framework + Ollama (qwen3:4b) / Demo Mode",
        facecolor="#DBEAFE",
        edgecolor="#1D4ED8",
        fontsize=9.5,
    )

    draw_box(
        ax,
        10.1,
        6.25,
        3.4,
        0.9,
        "Append-Only Execution Log",
        "logs/execution.jsonl\nTimestamped Agent & Tool Trace",
        facecolor="#F1F5F9",
        edgecolor="#475569",
        fontsize=9.5,
    )

    draw_arrow(ax, 3.7, 6.7, 4.6, 6.7, "#1D4ED8")
    draw_arrow(ax, 9.2, 6.7, 10.1, 6.7, "#475569")

    # Middle layer: 5 Agents in sequential pipeline
    agents = [
        (0.4, "1. Validation Agent", "check_product_exists\nvalidate_address | verify_payment"),
        (3.1, "2. Inventory Agent", "get_stock_level\nreserve_stock | suggest_substitute"),
        (5.8, "3. Fraud Check Agent", "get_customer_history\ncalculate_fraud_score | record_fraud_flag"),
        (8.5, "4. Pricing Agent", "get_product_price\ncalculate_discount | calculate_final_total"),
        (11.2, "5. Dispatch Coordinator", "select_shipping_method\ngenerate_tracking_id | confirm_dispatch"),
    ]
    for idx, (x, title, sub) in enumerate(agents):
        fc = "#FEF3C7" if idx == 2 else "#EFF6FF"
        ec = "#D97706" if idx == 2 else "#2563EB"
        draw_box(ax, x, 4.35, 2.4, 1.15, title, sub, facecolor=fc, edgecolor=ec, fontsize=8.8)

    # Pipeline arrows between agents
    draw_arrow(ax, 2.8, 4.92, 3.1, 4.92, "#16A34A", "VALID", 2.95, 5.26)
    draw_arrow(ax, 5.5, 4.92, 5.8, 4.92, "#16A34A", "RESERVED", 5.65, 5.26)
    draw_arrow(ax, 8.2, 4.92, 8.5, 4.92, "#16A34A", "LOW/MED", 8.35, 5.26)
    draw_arrow(ax, 10.9, 4.92, 11.2, 4.92, "#16A34A", "PRICED", 11.05, 5.26)

    # Orchestrator down to pipeline
    draw_arrow(ax, 6.9, 6.25, 6.9, 5.68, "#1D4ED8")
    ax.plot([1.6, 12.4], [5.68, 5.68], color="#93C5FD", lw=1.4, ls="--")
    for x, _, _ in agents:
        ax.plot([x + 1.2, x + 1.2], [5.68, 5.50], color="#93C5FD", lw=1.2)

    # Stop / Escalation / Final Decision Outcomes Row
    draw_box(
        ax,
        0.4,
        2.55,
        2.4,
        0.85,
        "REJECTED",
        "Invalid Product / Address /\nUnpaid Order (Stop)",
        facecolor="#FEE2E2",
        edgecolor="#DC2626",
        title_color="#991B1B",
        fontsize=8.8,
    )
    draw_box(
        ax,
        3.1,
        2.55,
        2.4,
        0.85,
        "SHORTFALL",
        "Insufficient Stock +\nSubstitute Suggested (Stop)",
        facecolor="#FEE2E2",
        edgecolor="#DC2626",
        title_color="#991B1B",
        fontsize=8.8,
    )
    draw_box(
        ax,
        5.8,
        2.55,
        2.4,
        0.85,
        "FRAUD HOLD QUEUE",
        "HELD_FOR_REVIEW (Score >= 60)\nNever Dispatched (Stop)",
        facecolor="#FEE2E2",
        edgecolor="#B91C1C",
        title_color="#991B1B",
        fontsize=8.8,
    )
    draw_box(
        ax,
        10.7,
        2.55,
        2.9,
        0.85,
        "CONFIRMED & DISPATCHED",
        "Shipping Method + Tracking ID\nDeterministic Final Payable Amount",
        facecolor="#DCFCE7",
        edgecolor="#16A34A",
        title_color="#166534",
        fontsize=8.8,
    )

    draw_arrow(ax, 1.6, 4.35, 1.6, 3.4, "#DC2626", "INVALID", 1.98, 3.88)
    draw_arrow(ax, 4.3, 4.35, 4.3, 3.4, "#DC2626", "SHORTFALL", 4.78, 3.88)
    draw_arrow(ax, 7.0, 4.35, 7.0, 3.4, "#B91C1C", "HIGH RISK", 7.48, 3.88)
    draw_arrow(ax, 12.4, 4.35, 12.15, 3.4, "#16A34A", "DISPATCHED", 12.78, 3.88)

    # Bottom shared resources layer
    draw_box(
        ax,
        0.5,
        0.45,
        4.1,
        1.25,
        "Shared OrderState Object",
        "core/order_state.py\nStatuses, Pricing, Fraud Score,\nTracking ID & Execution Trace",
        facecolor="#EDE9FE",
        edgecolor="#7C3AED",
        title_color="#4C1D95",
        fontsize=9.2,
    )
    draw_box(
        ax,
        5.0,
        0.45,
        4.1,
        1.25,
        "Persistent SQLite Memory",
        "memory/database.py (orders.db)\nCustomers, Products, Orders, Items &\nFraud Flags (Prior-Order History)",
        facecolor="#ECFEFF",
        edgecolor="#0891B2",
        title_color="#164E63",
        fontsize=9.2,
    )
    draw_box(
        ax,
        9.5,
        0.45,
        4.0,
        1.25,
        "Deterministic Python Tools",
        "tools/business_tools.py (15 Tools)\nAtomic Stock Reserve, Fraud Scoring,\nDiscount/Tax Math & Dispatch Guardrail",
        facecolor="#F0FDF4",
        edgecolor="#15803D",
        title_color="#14532D",
        fontsize=9.2,
    )

    # Connectors to shared resources
    ax.plot([0.5, 13.5], [2.05, 2.05], color="#94A3B8", lw=1.2, ls=":")
    ax.text(
        7.0,
        2.17,
        "Shared State, Persistent Memory & Tool Layer (Read / Written by All Five Agents)",
        ha="center",
        va="center",
        fontsize=8.2,
        color="#475569",
        style="italic",
    )
    draw_arrow(ax, 2.55, 2.05, 2.55, 1.7, "#7C3AED")
    draw_arrow(ax, 7.05, 2.05, 7.05, 1.7, "#0891B2")
    draw_arrow(ax, 11.5, 2.05, 11.5, 1.7, "#15803D")

    out_path = Path(__file__).resolve().parent.parent / "architecture.png"
    plt.tight_layout(pad=0.3)
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved architecture diagram to: {out_path}")


if __name__ == "__main__":
    main()
