"""VoltGear Commerce — Shopify-Style Storefront & Multi-Agent Admin Platform.

CSE476 – E-Commerce Order Fulfilment Orchestrator (Microsoft Agent Framework + Ollama qwen3:4b)
"""

from __future__ import annotations

import uuid
from typing import Any

import pandas as pd
import streamlit as st

from core.orchestrator import AGENT_ROSTER, OrderFulfilmentOrchestrator

st.set_page_config(
    page_title="VoltGear Store | Multi-Agent Commerce",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Product metadata for Shopify-style storefront cards (descriptions, ratings, crisp inline SVG artwork)
PRODUCT_PRESENTATION: dict[str, dict[str, Any]] = {
    "P101": {
        "tagline": "Active noise cancelling, 40h battery, Bluetooth 5.3",
        "rating": "4.8 (124)",
        "bg": "linear-gradient(135deg, #EEF2FF 0%, #DBEAFE 100%)",
        "svg": """<svg width="72" height="72" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M14 34V30C14 20.06 22.06 12 32 12C41.94 12 50 20.06 50 30V34" stroke="#1E40AF" stroke-width="4" stroke-linecap="round"/>
          <rect x="10" y="32" width="10" height="18" rx="5" fill="#2563EB"/>
          <rect x="44" y="32" width="10" height="18" rx="5" fill="#2563EB"/>
          <rect x="13" y="35" width="4" height="12" rx="2" fill="#93C5FD"/>
          <rect x="47" y="35" width="4" height="12" rx="2" fill="#93C5FD"/>
        </svg>""",
    },
    "P102": {
        "tagline": "AMOLED display, SpO2 & heart-rate monitor, 5ATM waterproof",
        "rating": "4.9 (218)",
        "bg": "linear-gradient(135deg, #ECFEFF 0%, #CFFAFE 100%)",
        "svg": """<svg width="72" height="72" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="24" y="8" width="16" height="10" rx="3" fill="#0E7490"/>
          <rect x="24" y="46" width="16" height="10" rx="3" fill="#0E7490"/>
          <rect x="17" y="16" width="30" height="32" rx="8" fill="#0F172A" stroke="#0891B2" stroke-width="3"/>
          <path d="M25 32L30 37L40 26" stroke="#38BDF8" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
    },
    "P103": {
        "tagline": "360° bass sound, IP67 splashproof, 18h portable playtime",
        "rating": "4.7 (89)",
        "bg": "linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%)",
        "svg": """<svg width="72" height="72" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="16" y="12" width="32" height="40" rx="8" fill="#4C1D95"/>
          <circle cx="32" cy="24" r="5" fill="#A78BFA"/>
          <circle cx="32" cy="40" r="8" fill="#7C3AED" stroke="#DDD6FE" stroke-width="2.5"/>
          <circle cx="32" cy="40" r="3" fill="#EDE9FE"/>
        </svg>""",
    },
    "P104": {
        "tagline": "20,000 mAh PD 22.5W fast-charge dual USB-C portable battery",
        "rating": "4.6 (156)",
        "bg": "linear-gradient(135deg, #FFF7ED 0%, #FFEDD5 100%)",
        "svg": """<svg width="72" height="72" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="18" y="10" width="28" height="44" rx="6" fill="#9A3412"/>
          <rect x="21" y="13" width="22" height="38" rx="4" fill="#EA580C"/>
          <path d="M34 21L26 33H32L30 43L38 31H32L34 21Z" fill="#FEF3C7"/>
        </svg>""",
    },
    "P105": {
        "tagline": "Compact tactile mechanical switches, white LED backlight",
        "rating": "4.8 (104)",
        "bg": "linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%)",
        "svg": """<svg width="72" height="72" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="8" y="18" width="48" height="28" rx="6" fill="#14532D"/>
          <rect x="13" y="23" width="6" height="5" rx="1" fill="#86EFAC"/>
          <rect x="21" y="23" width="6" height="5" rx="1" fill="#86EFAC"/>
          <rect x="29" y="23" width="6" height="5" rx="1" fill="#86EFAC"/>
          <rect x="37" y="23" width="6" height="5" rx="1" fill="#86EFAC"/>
          <rect x="45" y="23" width="6" height="5" rx="1" fill="#86EFAC"/>
          <rect x="13" y="31" width="8" height="5" rx="1" fill="#BBF7D0"/>
          <rect x="23" y="31" width="18" height="5" rx="1" fill="#4ADE80"/>
          <rect x="43" y="31" width="8" height="5" rx="1" fill="#BBF7D0"/>
        </svg>""",
    },
}

# Crisp Shopify-inspired CSS with guaranteed white inputs & dark readable text
st.markdown(
    """
    <style>
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
    }

    /* Guarantee crisp readable white form controls in main content */
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea,
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border-color: #CBD5E1 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    .stTextInput label,
    .stNumberInput label,
    .stSelectbox label,
    .stRadio label,
    .stMultiSelect label {
        color: #0F172A !important;
    }

    /* Compact, clean Shopify-admin dark navy sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0F172A !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1.25rem;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {
        color: #F1F5F9 !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        width: 100%;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
    }

    /* Storefront hero banner */
    .store-hero {
        background: linear-gradient(120deg, #0F172A 0%, #1E3A8A 100%);
        color: #FFFFFF;
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .store-hero h1 {
        color: #FFFFFF !important;
        margin: 0;
        font-size: 1.75rem;
        font-weight: 800;
    }
    .store-hero p {
        color: #CBD5E1 !important;
        margin: 6px 0 0 0;
        font-size: 0.95rem;
    }

    /* Uniform-height Shopify product cards */
    .shop-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        overflow: hidden;
        height: 295px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        margin-bottom: 10px;
    }
    .shop-card-img {
        height: 118px;
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
    }
    .shop-card-badge-wrap {
        position: absolute;
        top: 10px;
        right: 10px;
    }
    .shop-card-body {
        padding: 14px 16px 12px 16px;
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .shop-cat {
        font-size: 0.72rem;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .shop-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0F172A;
        margin: 3px 0 4px 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .shop-desc {
        font-size: 0.82rem;
        color: #475569;
        line-height: 1.35;
        height: 36px;
        overflow: hidden;
    }
    .shop-footer {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #F1F5F9;
    }
    .shop-price {
        font-size: 1.2rem;
        font-weight: 800;
        color: #0F172A;
    }
    .shop-rating {
        font-size: 0.78rem;
        color: #D97706;
        font-weight: 600;
    }

    /* Generic crisp white cards & metrics */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 15px 18px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }
    .card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }
    .page-title {
        font-size: 1.7rem;
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 0.15rem;
    }
    .page-sub {
        color: #475569;
        font-size: 0.94rem;
        margin-bottom: 1.15rem;
    }

    /* Status pills */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .badge-green { background: #DCFCE7; color: #166534; }
    .badge-red { background: #FEE2E2; color: #991B1B; }
    .badge-amber { background: #FEF3C7; color: #92400E; }
    .badge-blue { background: #DBEAFE; color: #1E40AF; }
    .badge-purple { background: #EDE9FE; color: #5B21B6; }
    .badge-gray { background: #E2E8F0; color: #334155; }

    .trace-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #2563EB;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
    }
    .trace-ok { border-left-color: #16A34A; }
    .trace-warn { border-left-color: #D97706; }
    .trace-err { border-left-color: #DC2626; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_orchestrator() -> OrderFulfilmentOrchestrator:
    return OrderFulfilmentOrchestrator()


def init_session_state() -> None:
    st.session_state.setdefault("cart", {})  # {product_id: quantity}
    st.session_state.setdefault("portal", "Customer")
    st.session_state.setdefault("customer_page", "Storefront")
    st.session_state.setdefault("admin_page", "Dashboard")
    st.session_state.setdefault("last_checkout_orders", [])
    st.session_state.setdefault("last_admin_state", None)
    st.session_state.setdefault("checkout_token", uuid.uuid4().hex)
    st.session_state.setdefault("requested_restocks", set())
    st.session_state.setdefault("restock_modal_pid", None)


def cart_item_count() -> int:
    return sum(int(q) for q in st.session_state.get("cart", {}).values())


def badge_html(label: str) -> str:
    s = (label or "PENDING").upper()
    if s == "DEMO":
        s = "AUTONOMOUS"
    if s in {"DISPATCHED", "VALID", "RESERVED", "LOW", "PRICED", "OK", "AVAILABLE", "SELECTED", "GENERATED", "VIP TRUSTED", "IN STOCK", "APPROVED", "ONLINE"}:
        cls = "badge-green"
    elif s in {"HELD_FOR_REVIEW", "HELD", "HIGH", "REJECTED", "INVALID", "SHORTFALL", "ERROR", "BLOCKED", "INSUFFICIENT", "OUT OF STOCK", "HIGH-RISK WATCHLIST", "CRITICAL"}:
        cls = "badge-red"
    elif s in {"MEDIUM", "FLAGGED", "SUGGESTED", "DEMO_FALLBACK", "CANCELLED", "LOW STOCK", "WATCH"}:
        cls = "badge-amber"
    elif s in {"PENDING_REVIEW", "OLLAMA", "RETRIEVED", "STANDARD", "STOREFRONT", "AUTONOMOUS", "LIVE_OLLAMA", "AI-AGENT"}:
        cls = "badge-blue"
    elif s in {"ADMIN_REVIEW"}:
        cls = "badge-purple"
    else:
        cls = "badge-gray"
    return f'<span class="badge {cls}">{s}</span>'


def trace_cls(result: str) -> str:
    r = (result or "").upper()
    if r in {"DISPATCHED", "VALID", "RESERVED", "LOW", "PRICED", "OK", "AVAILABLE", "SELECTED", "GENERATED", "APPROVED"}:
        return "trace-card trace-ok"
    if r in {"HELD_FOR_REVIEW", "HELD", "HIGH", "REJECTED", "INVALID", "SHORTFALL", "ERROR", "BLOCKED", "INSUFFICIENT"}:
        return "trace-card trace-err"
    if r in {"MEDIUM", "FLAGGED", "SUGGESTED", "DEMO_FALLBACK"}:
        return "trace-card trace-warn"
    return "trace-card"


def render_sidebar(orch: OrderFulfilmentOrchestrator) -> tuple[str, str, str]:
    with st.sidebar:
        st.markdown("## ⚡ VoltGear")
        st.caption("Shopify-Style Store & 5-Agent Ops")

        portal_choice = st.radio(
            "Workspace",
            ["🛍️ Customer Store", "🏢 Admin Console"],
            index=0 if st.session_state["portal"] == "Customer" else 1,
        )
        st.session_state["portal"] = "Customer" if portal_choice.startswith("🛍️") else "Admin"

        orders = orch.db.list_orders()
        pending_cnt = sum(1 for o in orders if o["decision"] == "PENDING_REVIEW")
        held_cnt = sum(1 for o in orders if o["decision"] == "HELD_FOR_REVIEW")
        cart_cnt = cart_item_count()

        if st.session_state["portal"] == "Customer":
            cust_pages = [
                "Storefront",
                f"Cart & Checkout ({cart_cnt})" if cart_cnt > 0 else "Cart & Checkout",
                "Track My Order",
            ]
            curr = st.session_state["customer_page"]
            idx = 0
            for i, p in enumerate(cust_pages):
                if p.startswith(curr):
                    idx = i
                    break
            picked = st.radio("Shop Menu", cust_pages, index=idx)
            clean_page = picked.split(" (")[0]
            st.session_state["customer_page"] = clean_page
        else:
            q_cnt = pending_cnt + held_cnt
            admin_pages = [
                "Dashboard",
                f"Order Approvals ({q_cnt})" if q_cnt > 0 else "Order Approvals",
                "Inventory & Restock",
                "Owner Insights",
                "Orders & AI Agents",
            ]
            curr = st.session_state["admin_page"]
            idx = 0
            for i, p in enumerate(admin_pages):
                if p.startswith(curr):
                    idx = i
                    break
            picked = st.radio("Admin Menu", admin_pages, index=idx)
            clean_page = picked.split(" (")[0]
            st.session_state["admin_page"] = clean_page

        st.divider()

        # Autonomous 5-Agent AI Engine status panel (unified live execution)
        ollama_ok, _ = orch.ollama_status()
        if ollama_ok:
            st.markdown(
                f"<div style='background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:8px 12px;margin-bottom:8px;'>"
                f"<div style='color:#166534;font-size:0.82rem;font-weight:600;'>🟢 5-Agent Engine: Live Ollama</div>"
                f"<div style='color:#15803D;font-size:0.75rem;'>Model: <code>{orch.ollama_model}</code> (Active)</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            mode = "OLLAMA"
        else:
            st.markdown(
                f"<div style='background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:8px 12px;margin-bottom:8px;'>"
                f"<div style='color:#0F172A;font-size:0.82rem;font-weight:600;'>⚡ 5-Agent Engine: Autonomous</div>"
                f"<div style='color:#64748B;font-size:0.75rem;'>15 Pure Python Verified Tools</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            mode = "DEMO"

        st.markdown(
            f"<div style='font-size:0.78rem;color:#94A3B8;margin-top:4px;margin-bottom:8px;'>"
            f"Active Agents: <strong>5 / 5 Ready</strong><br/>"
            f"Pending Queue: <strong>{pending_cnt}</strong> · Fraud Holds: <strong>{held_cnt}</strong>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button("🔄 Reset Store & Catalog Data", use_container_width=True):
            orch.db.reset_demo_data()
            st.session_state["cart"] = {}
            st.session_state["last_checkout_orders"] = []
            st.session_state["last_admin_state"] = None
            st.session_state["requested_restocks"] = set()
            st.session_state["restock_modal_pid"] = None
            st.toast("Store catalog, inventory & test customer profiles reset.", icon="✅")
            st.rerun()
            st.toast("Demo catalog, customers & orders restored.", icon="✅")
            st.rerun()

    return st.session_state["portal"], clean_page, mode


# =====================================================================
# PORTAL 1: SHOPIFY-STYLE CUSTOMER STOREFRONT
# =====================================================================

def render_storefront(orch: OrderFulfilmentOrchestrator) -> None:
    cart_cnt = cart_item_count()
    products = orch.db.list_products()

    # Shopify Store Hero Header
    st.markdown(
        f"""
        <div class="store-hero">
            <div>
                <h1>⚡ VoltGear Tech Store</h1>
                <p>Genuine audio, wearables &amp; everyday accessories · Free 5% discount on orders ₹{orch.rules.discount_threshold:,.0f}+ · AI-Verified Dispatch</p>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.8rem; color:#93C5FD; font-weight:600;">SHOPPING CART</div>
                <div style="font-size:1.35rem; font-weight:800; color:#FFFFFF;">{cart_cnt} item(s)</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Top filter bar + Quick Proceed to Checkout CTA
    f1, f2, f3 = st.columns([2.2, 1.5, 1.3])
    search_text = f1.text_input("Search products...", "", placeholder="Search headphones, watch, speaker, keyboard...", label_visibility="collapsed")
    categories = ["All Categories"] + sorted({p["category"] for p in products})
    selected_cat = f2.selectbox("Category", categories, label_visibility="collapsed")
    with f3:
        if cart_cnt > 0:
            if st.button(f"Proceed to Checkout ({cart_cnt}) →", type="primary", use_container_width=True):
                st.session_state["customer_page"] = "Cart & Checkout"
                st.rerun()
        else:
            st.button("Cart is Empty", disabled=True, use_container_width=True)

    filtered_products = [
        p
        for p in products
        if (selected_cat == "All Categories" or p["category"] == selected_cat)
        and (not search_text.strip() or search_text.strip().lower() in f"{p['name']} {p['category']} {p['product_id']}".lower())
    ]

    st.write("")
    if not filtered_products:
        st.info("No products matched your filter.")
        return

    # Uniform 3-column Shopify grid (3 cards per row -> every card identical height & width!)
    for row_start in range(0, len(filtered_products), 3):
        row_items = filtered_products[row_start : row_start + 3]
        cols = st.columns(3)
        for col, prod in zip(cols, row_items):
            pid = prod["product_id"]
            stock = int(prod["stock"])
            pres = PRODUCT_PRESENTATION.get(
                pid,
                {
                    "tagline": "Quality electronics accessory with warranty",
                    "rating": "4.7 (50)",
                    "bg": "linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%)",
                    "svg": "",
                },
            )
            if stock == 0:
                stock_pill = badge_html("OUT OF STOCK")
            elif stock <= 3:
                stock_pill = badge_html(f"ONLY {stock} LEFT")
            else:
                stock_pill = badge_html("IN STOCK")

            in_cart_qty = int(st.session_state["cart"].get(pid, 0))

            with col:
                st.markdown(
                    f"""
                    <div class="shop-card">
                        <div class="shop-card-img" style="background:{pres['bg']};">
                            <div class="shop-card-badge-wrap">{stock_pill}</div>
                            {pres['svg']}
                        </div>
                        <div class="shop-card-body">
                            <div>
                                <div class="shop-cat">{prod['category']} · {pid}</div>
                                <div class="shop-title">{prod['name']}</div>
                                <div class="shop-desc">{pres['tagline']}</div>
                            </div>
                            <div class="shop-footer">
                                <span class="shop-price">₹{prod['price']:,.0f}</span>
                                <span class="shop-rating">★ {pres['rating']}</span>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if stock > 0:
                    max_reached = in_cart_qty >= stock
                    if max_reached:
                        st.button(
                            f"Max Stock in Cart ({in_cart_qty}/{stock})",
                            key=f"add_{pid}",
                            disabled=True,
                            use_container_width=True,
                        )
                    else:
                        btn_text = (
                            f"+ Add Another ({in_cart_qty} in cart)"
                            if in_cart_qty > 0
                            else "Add to Cart"
                        )
                        if st.button(btn_text, key=f"add_{pid}", type="primary", use_container_width=True):
                            st.session_state["cart"][pid] = in_cart_qty + 1
                            st.toast(f"Added {prod['name']} to your cart!", icon="🛍️")
                            st.rerun()
                else:
                    # Out of stock: NEVER allow adding to cart; offer Request Restock instead!
                    already_req = pid in st.session_state["requested_restocks"]
                    if already_req:
                        st.button(
                            "✓ Restock Requested",
                            key=f"req_done_{pid}",
                            disabled=True,
                            use_container_width=True,
                        )
                    else:
                        if st.button("🔔 Request Restock", key=f"req_{pid}", use_container_width=True):
                            st.session_state["restock_modal_pid"] = pid
                            st.rerun()

        st.write("")

    # Compact inline Restock Request Panel when a customer clicks "Request Restock" on an out-of-stock item
    req_pid = st.session_state.get("restock_modal_pid")
    if req_pid:
        req_prod = next((p for p in products if p["product_id"] == req_pid), None)
        if req_prod and int(req_prod["stock"]) == 0:
            st.divider()
            st.subheader(f"🔔 Request Restock — {req_prod['name']} ({req_pid})")
            st.caption(
                "This item is currently out of stock and cannot be added to cart. Leave your name & contact below and we'll notify the store owner to restock it."
            )
            with st.form("restock_request_form"):
                r1, r2 = st.columns(2)
                req_name = r1.text_input("Your Name", placeholder="e.g. Aarav Sharma")
                req_contact = r2.text_input("Mobile Number or Email", placeholder="+91 98765 43210")
                b_sub, b_can = st.columns([1.5, 1])
                send_req = b_sub.form_submit_button("Send Restock Request", type="primary", use_container_width=True)
                cancel_req = b_can.form_submit_button("Cancel", use_container_width=True)
            if send_req:
                orch.db.create_restock_request(req_pid, req_name or "Storefront Customer", req_contact)
                st.session_state["requested_restocks"].add(req_pid)
                st.session_state["restock_modal_pid"] = None
                st.toast(f"Restock request sent to Admin for {req_prod['name']}!", icon="🔔")
                st.rerun()
            if cancel_req:
                st.session_state["restock_modal_pid"] = None
                st.rerun()


def render_cart_and_checkout(orch: OrderFulfilmentOrchestrator, mode: str) -> None:
    st.markdown('<div class="page-title">🛒 Cart & Checkout</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Review your cart, enter shipping & contact details, and place your order.</div>',
        unsafe_allow_html=True,
    )

    # Show Order Confirmation Banner if just placed
    recent_placed = st.session_state.get("last_checkout_orders") or []
    if recent_placed and not st.session_state["cart"]:
        st.success(f"Thank you! Your order has been received ({', '.join(recent_placed)}).")
        c_go1, c_go2 = st.columns(2)
        if c_go1.button("📍 Track My Order →", type="primary", use_container_width=True):
            st.session_state["customer_page"] = "Track My Order"
            st.rerun()
        if c_go2.button("🛍️ Continue Shopping", use_container_width=True):
            st.session_state["last_checkout_orders"] = []
            st.session_state["customer_page"] = "Storefront"
            st.rerun()
        st.divider()

    cart: dict[str, int] = st.session_state["cart"]
    if not cart:
        st.markdown(
            """
            <div class="card" style="text-align:center; padding:42px 20px;">
                <div style="font-size:2.5rem; margin-bottom:8px;">🛍️</div>
                <div style="font-size:1.2rem; font-weight:700; color:#0F172A;">Your shopping cart is empty</div>
                <div style="color:#64748B; margin-top:6px;">Browse the VoltGear Storefront and add items to begin checkout.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("← Browse Storefront", type="primary"):
            st.session_state["customer_page"] = "Storefront"
            st.rerun()
        return

    products_by_id = {p["product_id"]: p for p in orch.db.list_products()}

    # Two-column authentic Shopify Checkout Layout
    left_col, right_col = st.columns([1.45, 1.0], gap="large")

    # RIGHT COLUMN: Live Cart Items + Totals
    with right_col:
        st.subheader("Order Summary")
        subtotal = 0.0
        for pid, qty in list(cart.items()):
            prod = products_by_id.get(pid)
            if not prod:
                continue
            line_total = float(prod["price"]) * int(qty)
            subtotal += line_total
            stock = int(prod["stock"])

            with st.container():
                st.markdown(
                    f"""
                    <div class="card" style="padding:12px 14px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <strong>{prod['name']}</strong> <span style="color:#64748B;font-size:0.8rem;">({pid})</span><br/>
                                <span style="color:#475569;font-size:0.85rem;">₹{prod['price']:,.0f} × {qty} &nbsp;·&nbsp; Stock: {stock}</span>
                            </div>
                            <strong style="font-size:1.02rem;">₹{line_total:,.0f}</strong>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                q1, q2, q3 = st.columns([1, 1, 1.4])
                if q1.button("−", key=f"dec_{pid}", use_container_width=True):
                    if qty <= 1:
                        del st.session_state["cart"][pid]
                    else:
                        st.session_state["cart"][pid] = qty - 1
                    st.rerun()
                if q2.button("+", key=f"inc_{pid}", disabled=(qty >= stock), use_container_width=True):
                    st.session_state["cart"][pid] = qty + 1
                    st.rerun()
                if q3.button("Remove", key=f"rem_{pid}", use_container_width=True):
                    del st.session_state["cart"][pid]
                    st.rerun()

        discount = (
            round(subtotal * orch.rules.discount_rate, 2)
            if subtotal >= orch.rules.discount_threshold
            else 0.0
        )
        tax = round((subtotal - discount) * orch.rules.tax_rate, 2)
        grand_total = round(subtotal - discount + tax, 2)

        st.markdown(
            f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between; margin:6px 0;">
                    <span style="color:#475569;">Subtotal</span>
                    <strong>₹{subtotal:,.2f}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin:6px 0; color:#16A34A;">
                    <span>Auto Discount ({int(orch.rules.discount_rate*100)}% on ≥₹{orch.rules.discount_threshold:,.0f})</span>
                    <strong>-₹{discount:,.2f}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin:6px 0; color:#475569;">
                    <span>Sample GST / Tax ({int(orch.rules.tax_rate*100)}%)</span>
                    <span>₹{tax:,.2f}</span>
                </div>
                <div style="display:flex; justify-content:space-between; margin:6px 0; color:#475569;">
                    <span>Shipping</span>
                    <span style="color:#16A34A; font-weight:600;">Calculated on Verification</span>
                </div>
                <hr style="margin:10px 0; border-color:#E2E8F0;" />
                <div style="display:flex; justify-content:space-between; font-size:1.2rem;">
                    <strong>Total Payable</strong>
                    <strong style="color:#2563EB;">₹{grand_total:,.2f}</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # LEFT COLUMN: Shopify Shipping, Contact & Payment Form
    with left_col:
        st.subheader("Contact & Delivery Information")

        customers = orch.db.list_customers()
        default_phones = {
            "C101": "+91 98450 11223",
            "C102": "+91 98801 44556",
            "C103": "+91 98112 77889",
            "C104": "+91 98200 99001",
            "C105": "+91 98290 33445",
        }
        default_addresses = {
            "C101": "42 MG Road, Bengaluru, Karnataka 560001",
            "C102": "18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
            "C103": "77 Sector 18, Noida, Uttar Pradesh 201301",
            "C104": "901 Linking Road, Mumbai, Maharashtra 400050",
            "C105": "14 Civil Lines, Jaipur, Rajasthan 302006",
        }

        with st.expander("👤 Quick-Fill Saved Customer Profile (Optional)", expanded=False):
            profile_choices = ["Enter Manually (New Customer)"] + [
                f"{c['customer_id']} — {c['name']}" for c in customers
            ]
            chosen_prof = st.selectbox("Choose customer profile", profile_choices)

        prefill_cid = "C106"
        prefill_name = ""
        prefill_phone = ""
        prefill_addr = ""
        if chosen_prof != "Enter Manually (New Customer)":
            prefill_cid, prefill_name = chosen_prof.split(" — ", 1)
            prefill_phone = default_phones.get(prefill_cid, "+91 98765 43210")
            prefill_addr = default_addresses.get(prefill_cid, "")

        with st.form("shopify_checkout_form"):
            c1, c2 = st.columns(2)
            with c1:
                full_name = st.text_input("Full Name *", value=prefill_name, placeholder="e.g. Priya Nair")
                phone = st.text_input("Mobile Number *", value=prefill_phone, placeholder="+91 98765 43210")
            with c2:
                customer_id = st.text_input("Customer ID *", value=prefill_cid, placeholder="e.g. C106")
                payment_choice = st.selectbox(
                    "Payment Method *",
                    [
                        "UPI / Card (Paid Immediately)",
                        "Pay Later / Unpaid (Triggers Payment Check)",
                        "Simulate Failed Card Payment",
                    ],
                )

            address = st.text_input(
                "Delivery Address (House/Flat, Street, City, State, PIN) *",
                value=prefill_addr,
                placeholder="18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
            )

            fulfilment_option = st.radio(
                "Order Processing Flow",
                [
                    "Submit to Store Admin Approval Queue (Recommended — Admin verifies & dispatches)",
                    "Instant Autonomous 5-Agent Fulfilment (Instant Verification & Dispatch)",
                ],
                index=0,
            )

            pay_btn = st.form_submit_button(
                f"Complete Order · ₹{grand_total:,.2f}",
                type="primary",
                use_container_width=True,
            )

        if pay_btn:
            if not full_name.strip():
                st.error("Please enter your Full Name before placing the order.")
                return

            payment_status = (
                "PAID"
                if payment_choice.startswith("UPI")
                else ("UNPAID" if payment_choice.startswith("Pay Later") else "FAILED")
            )
            base_token = st.session_state["checkout_token"]
            st.session_state["checkout_token"] = uuid.uuid4().hex

            created_ids: list[str] = []
            for idx, (pid, qty) in enumerate(list(cart.items())):
                item_token = f"{base_token}-{idx}"
                if fulfilment_option.startswith("Submit to Store Admin"):
                    res = orch.submit_customer_order(
                        customer_id=customer_id,
                        customer_name=full_name,
                        customer_phone=phone,
                        product_id=pid,
                        quantity=int(qty),
                        address=address,
                        payment_status=payment_status,
                        idempotency_key=item_token,
                    )
                else:
                    with st.status(f"Processing {pid} via 5-Agent AI Pipeline...", expanded=True) as box:
                        res = orch.process_order(
                            customer_id=customer_id,
                            customer_name=full_name,
                            customer_phone=phone,
                            product_id=pid,
                            quantity=int(qty),
                            address=address,
                            payment_status=payment_status,
                            idempotency_key=item_token,
                            mode=mode,
                        )
                        box.update(
                            label=f"{res.order_id} → {res.decision}",
                            state="complete" if res.decision == "DISPATCHED" else "error",
                        )
                created_ids.append(res.order_id)

            st.session_state["cart"] = {}
            st.session_state["last_checkout_orders"] = created_ids
            st.rerun()


def render_track_order(orch: OrderFulfilmentOrchestrator) -> None:
    st.markdown('<div class="page-title">📦 Track Your Order</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Follow your order from checkout through AI verification, packing, and delivery ETA.</div>',
        unsafe_allow_html=True,
    )

    orders = orch.db.list_orders()
    if not orders:
        st.info("No orders found yet. Visit the Storefront to place your first order.")
        return

    order_ids = [o["order_id"] for o in orders]
    recent = st.session_state.get("last_checkout_orders") or []
    default_idx = order_ids.index(recent[0]) if recent and recent[0] in order_ids else 0

    selected_id = st.selectbox("Select Your Order ID", order_ids, index=default_idx)
    details = orch.db.get_order_details(selected_id)
    if not details:
        return

    item = details["items"][0] if details.get("items") else {}
    st.markdown(
        f"""
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-size:1.25rem; font-weight:800;">Order {details['order_id']}</div>
                    <div style="color:#475569; font-size:0.9rem;">{details['customer_name']} ({details['customer_id']}) · {details.get('customer_phone') or 'No phone'}</div>
                </div>
                <div>{badge_html(details['decision'])}</div>
            </div>
            <hr style="margin:12px 0; border-color:#E2E8F0;" />
            <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px;">
                <div><span style="color:#64748B;font-size:0.8rem;">Item</span><br/><strong>{item.get('product_name', '-')} × {item.get('quantity', 0)}</strong></div>
                <div><span style="color:#64748B;font-size:0.8rem;">Total Payable</span><br/><strong>₹{details['final_total']:,.2f}</strong></div>
                <div><span style="color:#64748B;font-size:0.8rem;">Tracking ID</span><br/><strong>{details.get('tracking_id') or 'Pending Dispatch'}</strong></div>
                <div><span style="color:#64748B;font-size:0.8rem;">Expected Delivery</span><br/><strong>{details.get('delivery_eta_window') or details.get('expected_delivery_date') or 'Awaiting Admin Approval'}</strong></div>
            </div>
            <div style="margin-top:12px; color:#334155; font-size:0.88rem;">
                <strong>Deliver To:</strong> {details['address']} &nbsp;|&nbsp;
                <strong>Courier:</strong> {details.get('shipping_method') or 'Assigned after verification'}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("5-Stage Fulfilment Pipeline Progress")
    cols = st.columns(5)
    stages = [
        ("1. Validation", details["validation_status"]),
        ("2. Stock Reserve", details["inventory_status"]),
        ("3. Fraud Check", f"{details['fraud_status']} ({details['fraud_score']})"),
        ("4. Pricing", details["pricing_status"]),
        ("5. Dispatch", details["dispatch_status"]),
    ]
    for col, (label, val) in zip(cols, stages):
        col.markdown(
            f'<div class="card" style="text-align:center;padding:12px;">'
            f'<div style="font-weight:700;font-size:0.88rem;margin-bottom:6px;">{label}</div>'
            f'{badge_html(val.split()[0])}'
            f'<div style="font-size:0.78rem;color:#64748B;margin-top:5px;">{val}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if details.get("hold_reason"):
        if details["decision"] == "PENDING_REVIEW":
            st.info(f"**Next Step:** {details['hold_reason']} (Switch to **Admin Console → Order Approvals** to verify and dispatch.)")
        else:
            st.warning(f"**Update:** {details['hold_reason']}")


# =====================================================================
# PORTAL 2: SHOPIFY ADMIN OPERATIONS CONSOLE
# =====================================================================

def render_admin_dashboard(orch: OrderFulfilmentOrchestrator) -> None:
    st.markdown('<div class="page-title">Executive Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Store revenue, order fulfilment conversion, pending approvals, and fraud protection at a glance.</div>',
        unsafe_allow_html=True,
    )

    metrics = orch.db.get_dashboard_metrics()
    insights = orch.db.get_owner_insights()

    if insights["pending_count"] > 0 or insights["held_count"] > 0:
        b_col1, b_col2 = st.columns([3.5, 1.2])
        b_col1.info(
            f"**Action Required:** **{insights['pending_count']}** incoming storefront order(s) awaiting verification "
            f"and **{insights['held_count']}** order(s) in Fraud Hold Review."
        )
        if b_col2.button("Open Approvals Queue →", type="primary", use_container_width=True):
            st.session_state["admin_page"] = "Order Approvals"
            st.rerun()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Orders", metrics["total_orders"])
    k2.metric("Dispatched", metrics["dispatched_orders"])
    k3.metric("Awaiting Review", insights["pending_count"] + insights["held_count"])
    k4.metric("Net Revenue", f"₹{metrics['total_processed_value']:,.2f}")
    k5.metric("Fulfilment Rate", f"{insights['conversion_rate']}%")

    st.write("")
    left, right = st.columns([1.45, 1.0])

    with left:
        st.subheader("Order Status Breakdown")
        counts = metrics["status_counts"]
        if counts:
            chart_df = pd.DataFrame({"Status": list(counts.keys()), "Orders": list(counts.values())}).set_index("Status")
            st.bar_chart(chart_df, color="#2563EB", height=265)
        else:
            st.info("No orders recorded yet.")

    with right:
        st.subheader("Store Health Summary")
        st.markdown(
            f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between; margin:8px 0;">
                    <span style="color:#475569;">Average Dispatched Order Value</span>
                    <strong>₹{insights['avg_order_value']:,.2f}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin:8px 0;">
                    <span style="color:#475569;">Protected in Fraud Hold Queue</span>
                    <strong style="color:#D97706;">₹{insights['held_value']:,.2f}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin:8px 0;">
                    <span style="color:#475569;">Stockout Lost Revenue</span>
                    <strong style="color:#DC2626;">₹{insights['shortfall_loss']:,.2f}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin:8px 0;">
                    <span style="color:#475569;">Low / Out-of-Stock Products</span>
                    <strong>{len(insights['restock_alerts'])} SKU(s)</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Recent Orders")
    orders = orch.db.list_orders()[:8]
    if orders:
        df = pd.DataFrame(orders)[
            [
                "order_id",
                "customer_name",
                "product_name",
                "quantity",
                "final_total",
                "fraud_status",
                "decision",
                "tracking_id",
                "expected_delivery_date",
            ]
        ]
        df.columns = [
            "Order ID",
            "Customer",
            "Product",
            "Qty",
            "Total (₹)",
            "Fraud",
            "Status",
            "Tracking ID",
            "Expected Delivery",
        ]
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_admin_approvals(orch: OrderFulfilmentOrchestrator, mode: str) -> None:
    st.markdown('<div class="page-title">Order Approvals & 5-Agent Dispatch</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Validate incoming customer orders (stock, address, contact, anti-spam & fraud history), generate Tracking IDs + Expected Delivery Dates, and resolve fraud holds.</div>',
        unsafe_allow_html=True,
    )

    orders = orch.db.list_orders()
    pending = [o for o in orders if o["decision"] == "PENDING_REVIEW"]
    held = [o for o in orders if o["decision"] == "HELD_FOR_REVIEW"]

    t_in, t_fraud, t_quick = st.tabs(
        [
            f"📥 Incoming Storefront Orders ({len(pending)})",
            f"🚨 Fraud Hold Queue ({len(held)})",
            "⚡ Direct Admin Test Order",
        ]
    )

    with t_in:
        if not pending:
            st.info(
                "No pending orders waiting for approval. Switch to **🛍️ Customer Store → Storefront**, "
                "add an item to cart, and complete checkout to test the end-to-end Shopify → Admin AI approval flow!"
            )
        else:
            for order in pending:
                prod = orch.db.get_product(order["product_id"])
                live_stock = int(prod["stock"]) if prod else 0
                stock_ok = live_stock >= int(order["quantity"])

                st.markdown(
                    f"""
                    <div class="card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <strong style="font-size:1.05rem;">{order['order_id']}</strong> ·
                                <strong>{order['customer_name']}</strong> ({order['customer_id']}) ·
                                <span style="color:#475569;">📞 {order.get('customer_phone') or 'No phone'}</span>
                            </div>
                            <div>{badge_html('PENDING_REVIEW')} {badge_html(order['payment_status'])}</div>
                        </div>
                        <div style="margin-top:8px; color:#334155; font-size:0.9rem;">
                            <strong>Item:</strong> {order['product_name']} ({order['product_id']}) × {order['quantity']}
                            &nbsp;|&nbsp; <strong>Live Stock:</strong> {live_stock} ({'Sufficient' if stock_ok else 'Shortfall Risk'})
                            &nbsp;|&nbsp; <strong>Subtotal:</strong> ₹{order['subtotal']:,.2f}<br/>
                            <strong>Address:</strong> {order['address']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    "🤖 Run 5-Agent Verification & Dispatch",
                    key=f"verify_{order['order_id']}",
                    type="primary",
                ):
                    with st.status(f"Running 5 Agents on {order['order_id']}...", expanded=True) as box:
                        st_res = orch.process_pending_order(order["order_id"], mode=mode)
                        box.update(
                            label=f"{st_res.order_id} → {st_res.decision}",
                            state="complete" if st_res.decision == "DISPATCHED" else "error",
                        )
                    st.session_state["last_admin_state"] = st_res
                    st.rerun()

        last_state = st.session_state.get("last_admin_state")
        if last_state is not None:
            st.divider()
            st.subheader(f"Latest 5-Agent Verification Outcome — {last_state.order_id}")
            st.markdown(
                f"**Decision:** {badge_html(last_state.decision)} &nbsp; "
                f"**Mode:** {badge_html(last_state.execution_mode)} &nbsp; "
                f"**Fraud Score:** `{last_state.fraud_score}/100` ({last_state.fraud_status})",
                unsafe_allow_html=True,
            )
            if last_state.decision == "DISPATCHED":
                st.success(
                    f"**Confirmed & Dispatched!** Tracking ID: **`{last_state.tracking_id}`** | "
                    f"Courier: **{last_state.shipping_method}** | "
                    f"Expected Delivery: **{last_state.delivery_eta_window}** | "
                    f"Final Total: **₹{last_state.final_total:,.2f}**"
                )
            elif last_state.decision == "HELD_FOR_REVIEW":
                st.error(f"**Escalated to Fraud Hold Queue:** {last_state.hold_reason}")
            else:
                st.warning(f"**Stopped ({last_state.decision}):** {last_state.hold_reason}")

            if last_state.agent_summaries:
                with st.expander("Agent-by-Agent Verification Details", expanded=True):
                    for ag_name, summary in last_state.agent_summaries.items():
                        st.markdown(f"- **{ag_name}:** {summary}")

    with t_fraud:
        if not held:
            st.success("No orders currently held in Fraud Review.")
        else:
            for order in held:
                st.markdown(
                    f"""
                    <div class="card" style="border-left:4px solid #DC2626;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <strong style="font-size:1.05rem;">{order['order_id']}</strong> ·
                                <span>{order['customer_name']} ({order['customer_id']})</span> ·
                                <span style="color:#991B1B;font-weight:700;">Fraud Score: {order['fraud_score']}/100</span>
                            </div>
                            <div>{badge_html('HELD_FOR_REVIEW')}</div>
                        </div>
                        <div style="margin-top:8px; color:#334155; font-size:0.9rem;">
                            <strong>Item:</strong> {order['product_name']} × {order['quantity']} &nbsp;|&nbsp;
                            <strong>Address:</strong> {order['address']}<br/>
                            <strong>Reason:</strong> {order.get('hold_reason') or 'High fraud score.'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                note = st.text_input(
                    "Admin Decision Note",
                    value="Verified customer ID via phone" if order["customer_id"] != "C104" else "Confirmed repeat failed-payment fraud risk",
                    key=f"note_{order['order_id']}",
                )
                a1, a2 = st.columns(2)
                if a1.button("✅ Approve & Dispatch Override", key=f"app_{order['order_id']}", type="primary", use_container_width=True):
                    res = orch.admin_resolve_held_order(order["order_id"], "APPROVE", note)
                    st.session_state["last_admin_state"] = res
                    st.toast(f"Approved & Dispatched {res.order_id} ({res.tracking_id})", icon="✅")
                    st.rerun()
                if a2.button("🛑 Reject Fraud & Restock Stock", key=f"rej_{order['order_id']}", use_container_width=True):
                    res = orch.admin_resolve_held_order(order["order_id"], "REJECT", note)
                    st.session_state["last_admin_state"] = res
                    st.toast(f"Rejected {res.order_id} and released reserved stock.", icon="🛑")
                    st.rerun()

    with t_quick:
        st.caption("Quickly simulate any test scenario directly through the 5-agent backend.")
        products = orch.db.list_products()
        customers = orch.db.list_customers()
        with st.form("admin_quick_form"):
            q1, q2 = st.columns(2)
            with q1:
                c_pick = st.selectbox("Customer", [f"{c['customer_id']} — {c['name']}" for c in customers])
                cid, cname = c_pick.split(" — ", 1)
                p_pick = st.selectbox(
                    "Product",
                    [f"{p['product_id']} — {p['name']} (₹{p['price']:,.0f} | Stock: {p['stock']})" for p in products],
                )
                pid = p_pick.split(" — ", 1)[0]
                phone = st.text_input("Contact Phone", value="+91 98765 43210")
            with q2:
                qty = st.number_input("Quantity", min_value=1, max_value=20, value=1)
                pay = st.selectbox("Payment Status", ["PAID", "UNPAID", "FAILED"])
                addr = st.text_input("Delivery Address", value="18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038")
            go = st.form_submit_button("⚡ Run 5-Agent Fulfilment Pipeline", type="primary", use_container_width=True)
        if go:
            with st.status("Running 5-Agent Fulfilment Pipeline...", expanded=True) as box:
                res = orch.process_order(
                    customer_id=cid,
                    customer_name=cname,
                    customer_phone=phone,
                    product_id=pid,
                    quantity=int(qty),
                    address=addr,
                    payment_status=pay,
                    mode=mode,
                )
                box.update(
                    label=f"{res.order_id} → {res.decision}",
                    state="complete" if res.decision == "DISPATCHED" else "error",
                )
            st.session_state["last_admin_state"] = res
            st.rerun()


def render_admin_inventory(orch: OrderFulfilmentOrchestrator) -> None:
    st.markdown('<div class="page-title">Live Inventory & Restock Manager</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Monitor live stock across all SKUs and restock low or out-of-stock products immediately.</div>',
        unsafe_allow_html=True,
    )

    products = orch.db.list_products()
    open_requests = orch.db.list_restock_requests("OPEN")
    req_counts = orch.db.get_open_restock_counts()

    total_units = sum(int(p["stock"]) for p in products)
    oos = sum(1 for p in products if int(p["stock"]) == 0)
    low = sum(1 for p in products if 0 < int(p["stock"]) <= 3)
    inv_val = sum(int(p["stock"]) * float(p["price"]) for p in products)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Catalog SKUs", len(products))
    m2.metric("Total Units Available", total_units)
    m3.metric("Stock Alerts", f"{oos} Out · {low} Low")
    m4.metric("Customer Restock Requests", len(open_requests))

    if open_requests:
        st.info(
            f"🔔 **{len(open_requests)} customer restock request(s)** waiting! Restocking an item below automatically marks its requests as fulfilled."
        )

    st.write("")
    for prod in products:
        stock = int(prod["stock"])
        status = "OUT OF STOCK" if stock == 0 else ("LOW STOCK" if stock <= 3 else "IN STOCK")
        cust_reqs = req_counts.get(prod["product_id"], 0)
        req_pill = f" &nbsp; {badge_html(f'{cust_reqs} RESTOCK REQ')}" if cust_reqs > 0 else ""
        c1, c2, c3, c4 = st.columns([2.2, 1.5, 0.9, 1.3])
        with c1:
            st.markdown(
                f"**{prod['product_id']} — {prod['name']}**{req_pill}  \n"
                f"<span style='color:#64748B;font-size:0.84rem;'>{prod['category']} · ₹{prod['price']:,.0f} · Substitute: {prod['substitute_id'] or 'None'}</span>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f"{badge_html(status)} &nbsp; **{stock} units**", unsafe_allow_html=True)
            st.progress(min(1.0, stock / 20.0))
        with c3:
            add_qty = st.number_input(
                "Qty",
                min_value=1,
                max_value=100,
                value=10 if stock == 0 else 5,
                key=f"inv_qty_{prod['product_id']}",
                label_visibility="collapsed",
            )
        with c4:
            if st.button(f"+ Restock {prod['product_id']}", key=f"inv_btn_{prod['product_id']}", use_container_width=True):
                new_lvl = orch.db.restock_product(prod["product_id"], int(add_qty))
                st.toast(f"Restocked {prod['name']} → {new_lvl} units!", icon="📦")
                st.rerun()
        st.divider()


def render_owner_insights(orch: OrderFulfilmentOrchestrator) -> None:
    st.markdown('<div class="page-title">✨ Owner Intelligence Hub</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Unique store-owner toolkit: recover lost stockout revenue, monitor customer trust tiers, and simulate live fraud & margin policies.</div>',
        unsafe_allow_html=True,
    )

    insights = orch.db.get_owner_insights()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Revenue at Risk", f"₹{insights['total_revenue_at_risk']:,.2f}")
    k2.metric("Stockout Lost Demand", f"₹{insights['shortfall_loss']:,.2f}")
    k3.metric("Fraud Hold Exposure", f"₹{insights['held_value']:,.2f}")
    k4.metric("Avg Dispatched Order", f"₹{insights['avg_order_value']:,.2f}")

    st.write("")
    t1, t2, t3 = st.tabs(
        [
            "💡 Smart Restock & Recovery",
            "🛡️ Customer Trust Leaderboard",
            "🎛️ Live Policy 'What-If' Simulator",
        ]
    )

    with t1:
        alerts = insights["restock_alerts"]
        if not alerts:
            st.success("Zero stockout alerts — all products have healthy inventory!")
        else:
            for a in alerts:
                ci, cb = st.columns([3.2, 1.2])
                with ci:
                    st.markdown(
                        f"""
                        <div class="card">
                            <div style="display:flex; justify-content:space-between;">
                                <strong>{a['product_id']} — {a['name']}</strong>
                                {badge_html(a['priority'])}
                            </div>
                            <div style="color:#475569;font-size:0.9rem;margin-top:6px;">
                                Current Stock: <strong>{a['current_stock']}</strong> ·
                                Customer Restock Requests: <strong>{a.get('customer_requests', 0)}</strong> ·
                                Missed Units: <strong>{a['missed_units']}</strong> ·
                                Lost Demand: <strong style="color:#DC2626;">₹{a['lost_revenue']:,.2f}</strong> ·
                                Recommended Restock: <strong>+{a['recommended_restock']} units</strong>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with cb:
                    st.write("")
                    if st.button(f"Restock +{a['recommended_restock']}", key=f"sr_{a['product_id']}", type="primary", use_container_width=True):
                        lvl = orch.db.restock_product(a["product_id"], a["recommended_restock"])
                        st.toast(f"{a['name']} restocked to {lvl} units!", icon="✅")
                        st.rerun()

    with t2:
        trust_df = pd.DataFrame(insights["customer_trust"])
        if not trust_df.empty:
            trust_df.columns = [
                "Customer ID",
                "Name",
                "Trust Score",
                "Tier",
                "Completed",
                "Failed Pay",
                "Cancelled",
                "Fraud Flags",
                "Lifetime Spend (₹)",
            ]
            st.dataframe(trust_df, use_container_width=True, hide_index=True)

    with t3:
        s1, s2, s3 = st.columns(3)
        sim_fraud = s1.slider("Fraud Hold Threshold", 20, 90, int(orch.rules.fraud_hold_threshold), 5)
        sim_disc_th = s2.slider("Discount Min Order (₹)", 1000, 8000, int(orch.rules.discount_threshold), 500)
        sim_disc_pct = s3.slider("Discount Rate (%)", 0, 20, int(round(orch.rules.discount_rate * 100)), 1)

        all_orders = orch.db.list_orders()
        would_hold = sum(1 for o in all_orders if int(o["fraud_score"] or 0) >= sim_fraud)
        dispatched = [o for o in all_orders if o["decision"] == "DISPATCHED"]
        sim_rev = 0.0
        sim_disc_cost = 0.0
        for o in dispatched:
            sub = float(o["subtotal"] or 0.0)
            disc = round(sub * (sim_disc_pct / 100.0), 2) if sub >= sim_disc_th else 0.0
            tax = round((sub - disc) * orch.rules.tax_rate, 2)
            sim_disc_cost += disc
            sim_rev += sub - disc + tax

        p1, p2, p3 = st.columns(3)
        p1.metric("Orders Flagged for Hold", f"{would_hold} / {len(all_orders)}")
        p2.metric("Projected Discount Spend", f"₹{sim_disc_cost:,.2f}")
        p3.metric("Projected Net Revenue", f"₹{sim_rev:,.2f}")

        if st.button("Apply Simulated Policy Live", type="primary"):
            orch.rules.fraud_hold_threshold = int(sim_fraud)
            orch.rules.discount_threshold = float(sim_disc_th)
            orch.rules.discount_rate = float(sim_disc_pct) / 100.0
            st.success(f"Applied live: Fraud Hold ≥ {sim_fraud} | {sim_disc_pct}% discount on ≥ ₹{sim_disc_th:,}.")


def render_orders_and_agents(orch: OrderFulfilmentOrchestrator) -> None:
    st.markdown('<div class="page-title">Orders & 5-Agent Audit Trace</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Searchable SQLite order registry plus live 5-Agent Microsoft Agent Framework roster and append-only JSONL execution trace.</div>',
        unsafe_allow_html=True,
    )

    tab_orders, tab_agents = st.tabs(["📋 All Orders & Inspector", "🤖 5-Agent Activity & Audit Log"])

    with tab_orders:
        orders = orch.db.list_orders()
        if not orders:
            st.info("No orders stored yet.")
        else:
            f1, f2 = st.columns([2, 1])
            q = f1.text_input("Search Order ID, Customer, Product, or Tracking ID", "").strip().lower()
            decisions = sorted({o["decision"] for o in orders})
            sel_dec = f2.multiselect("Filter Status", decisions, default=decisions)
            filtered = [
                o
                for o in orders
                if o["decision"] in sel_dec
                and (
                    not q
                    or q in " ".join(str(o.get(k, "") or "") for k in ("order_id", "customer_id", "customer_name", "product_name", "tracking_id")).lower()
                )
            ]
            if not filtered:
                st.warning("No matching orders.")
            else:
                df = pd.DataFrame(filtered)[
                    [
                        "order_id",
                        "customer_name",
                        "product_name",
                        "quantity",
                        "final_total",
                        "fraud_score",
                        "decision",
                        "tracking_id",
                        "expected_delivery_date",
                    ]
                ]
                df.columns = ["Order ID", "Customer", "Product", "Qty", "Total (₹)", "Fraud Score", "Status", "Tracking ID", "Expected Delivery"]
                st.dataframe(df, use_container_width=True, hide_index=True)

                st.divider()
                pick = st.selectbox("Inspect Order Details", [o["order_id"] for o in filtered])
                details = orch.db.get_order_details(pick)
                if details:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"**Order ID:** `{details['order_id']}`")
                        st.markdown(f"**Customer:** {details['customer_name']} (`{details['customer_id']}`)")
                        st.markdown(f"**Phone:** {details.get('customer_phone') or '—'}")
                        st.markdown(f"**Address:** {details['address']}")
                    with c2:
                        st.markdown(f"**Status:** {badge_html(details['decision'])}", unsafe_allow_html=True)
                        st.markdown(f"**Fraud:** {badge_html(details['fraud_status'])} (`{details['fraud_score']}/100`)", unsafe_allow_html=True)
                        st.markdown(f"**Tracking ID:** `{details.get('tracking_id') or '—'}`")
                        st.markdown(f"**Delivery ETA:** {details.get('delivery_eta_window') or details.get('expected_delivery_date') or '—'}")
                    with c3:
                        st.markdown(f"**Subtotal:** ₹{details['subtotal']:,.2f}")
                        st.markdown(f"**Discount:** -₹{details['discount']:,.2f}")
                        st.markdown(f"**Tax:** ₹{details['tax']:,.2f}")
                        st.markdown(f"**Final Total:** **₹{details['final_total']:,.2f}**")
                    if details.get("hold_reason"):
                        st.warning(f"**Note:** {details['hold_reason']}")

    with tab_agents:
        all_logs = orch.logger.read_all()
        counts_by_agent: dict[str, int] = {}
        for entry in all_logs:
            ag = entry.get("agent_name", "")
            counts_by_agent[ag] = counts_by_agent.get(ag, 0) + 1

        st.subheader("Five-Agent Pipeline Roster (Microsoft Agent Framework)")
        roster_df = pd.DataFrame(
            [
                {
                    "Stage": r["stage"],
                    "Agent": r["name"],
                    "Module": r["module"],
                    "Role": r["role"],
                    "Registered Python Tools": ", ".join(r["tools"]),
                    "Logged Tool Calls": counts_by_agent.get(r["name"], 0),
                }
                for r in AGENT_ROSTER
            ]
        )
        st.dataframe(roster_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Append-Only Execution Trace (logs/execution.jsonl)")
        if not all_logs:
            st.info("No execution logs yet.")
        else:
            order_ids = list(dict.fromkeys(reversed([e["order_id"] for e in all_logs])))
            sel_oid = st.selectbox("Select Order Execution Trace", order_ids)
            entries = [e for e in all_logs if e["order_id"] == sel_oid]
            for entry in entries:
                st.markdown(
                    f"""
                    <div class="{trace_cls(entry.get('result', ''))}">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div><strong>{entry.get('agent_name')}</strong> · <code>{entry.get('tool_used')}</code> ({entry.get('action')})</div>
                            <div>{badge_html(entry.get('result', ''))} <span style="color:#64748B;font-size:0.8rem;margin-left:6px;">{entry.get('timestamp')} · {entry.get('execution_mode')}</span></div>
                        </div>
                        <div style="margin-top:6px; color:#334155; font-size:0.9rem;">{entry.get('explanation')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def main() -> None:
    init_session_state()
    orch = get_orchestrator()
    portal, page, mode = render_sidebar(orch)

    if portal == "Customer":
        if page == "Storefront":
            render_storefront(orch)
        elif page == "Cart & Checkout":
            render_cart_and_checkout(orch, mode)
        else:
            render_track_order(orch)
    else:
        if page == "Dashboard":
            render_admin_dashboard(orch)
        elif page == "Order Approvals":
            render_admin_approvals(orch, mode)
        elif page == "Inventory & Restock":
            render_admin_inventory(orch)
        elif page == "Owner Insights":
            render_owner_insights(orch)
        else:
            render_orders_and_agents(orch)


if __name__ == "__main__":
    main()
