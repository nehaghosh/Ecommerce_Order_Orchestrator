"""SQLite database layer for persistent customer memory, inventory, and orders."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from core.order_state import OrderState, utc_now_iso


DEFAULT_CUSTOMERS = [
    ("C101", "Aarav Sharma", "aarav.sharma@example.com"),
    ("C102", "Priya Nair", "priya.nair@example.com"),
    ("C103", "Rohan Verma", "rohan.verma@example.com"),
    ("C104", "Vikram Mehta", "vikram.mehta@example.com"),
    ("C105", "Ananya Iyer", "ananya.iyer@example.com"),
]

# Sample historical orders seeded once so Fraud Check Agent has realistic prior-order memory.
# Clearly demonstration data only (not real transactions).
DEFAULT_HISTORICAL_ORDERS = [
    # C101: Normal customer (1 successful past order)
    {
        "order_id": "ORD-HIST-101",
        "customer_id": "C101",
        "customer_name": "Aarav Sharma",
        "address": "42 MG Road, Bengaluru, Karnataka 560001",
        "payment_status": "PAID",
        "validation_status": "VALID",
        "inventory_status": "RESERVED",
        "fraud_status": "LOW",
        "pricing_status": "PRICED",
        "dispatch_status": "DISPATCHED",
        "fraud_score": 0,
        "subtotal": 2000.0,
        "discount": 0.0,
        "tax": 360.0,
        "final_total": 2360.0,
        "shipping_method": "Express Metro Courier",
        "tracking_id": "TRK-HIST101",
        "decision": "DISPATCHED",
        "hold_reason": None,
        "execution_mode": "SEED",
        "product_id": "P101",
        "product_name": "Wireless Headphones",
        "quantity": 1,
        "unit_price": 2000.0,
        "created_at": "2026-10-10T09:15:00Z",
    },
    # C102: Repeat trusted customer (4 successful past orders)
    {
        "order_id": "ORD-HIST-201",
        "customer_id": "C102",
        "customer_name": "Priya Nair",
        "address": "18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
        "payment_status": "PAID",
        "validation_status": "VALID",
        "inventory_status": "RESERVED",
        "fraud_status": "LOW",
        "pricing_status": "PRICED",
        "dispatch_status": "DISPATCHED",
        "fraud_score": 0,
        "subtotal": 3500.0,
        "discount": 175.0,
        "tax": 598.5,
        "final_total": 3923.5,
        "shipping_method": "Express Metro Courier",
        "tracking_id": "TRK-HIST201",
        "decision": "DISPATCHED",
        "hold_reason": None,
        "execution_mode": "SEED",
        "product_id": "P102",
        "product_name": "Smart Watch",
        "quantity": 1,
        "unit_price": 3500.0,
        "created_at": "2026-09-05T11:00:00Z",
    },
    {
        "order_id": "ORD-HIST-202",
        "customer_id": "C102",
        "customer_name": "Priya Nair",
        "address": "18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
        "payment_status": "PAID",
        "validation_status": "VALID",
        "inventory_status": "RESERVED",
        "fraud_status": "LOW",
        "pricing_status": "PRICED",
        "dispatch_status": "DISPATCHED",
        "fraud_score": 0,
        "subtotal": 1500.0,
        "discount": 0.0,
        "tax": 270.0,
        "final_total": 1770.0,
        "shipping_method": "Express Metro Courier",
        "tracking_id": "TRK-HIST202",
        "decision": "DISPATCHED",
        "hold_reason": None,
        "execution_mode": "SEED",
        "product_id": "P103",
        "product_name": "Bluetooth Speaker",
        "quantity": 1,
        "unit_price": 1500.0,
        "created_at": "2026-09-20T14:30:00Z",
    },
    {
        "order_id": "ORD-HIST-203",
        "customer_id": "C102",
        "customer_name": "Priya Nair",
        "address": "18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
        "payment_status": "PAID",
        "validation_status": "VALID",
        "inventory_status": "RESERVED",
        "fraud_status": "LOW",
        "pricing_status": "PRICED",
        "dispatch_status": "DISPATCHED",
        "fraud_score": 0,
        "subtotal": 1200.0,
        "discount": 0.0,
        "tax": 216.0,
        "final_total": 1416.0,
        "shipping_method": "Express Metro Courier",
        "tracking_id": "TRK-HIST203",
        "decision": "DISPATCHED",
        "hold_reason": None,
        "execution_mode": "SEED",
        "product_id": "P105",
        "product_name": "Keyboard",
        "quantity": 1,
        "unit_price": 1200.0,
        "created_at": "2026-10-02T16:45:00Z",
    },
    {
        "order_id": "ORD-HIST-204",
        "customer_id": "C102",
        "customer_name": "Priya Nair",
        "address": "18 Indiranagar 100ft Rd, Bengaluru, Karnataka 560038",
        "payment_status": "PAID",
        "validation_status": "VALID",
        "inventory_status": "RESERVED",
        "fraud_status": "LOW",
        "pricing_status": "PRICED",
        "dispatch_status": "DISPATCHED",
        "fraud_score": 0,
        "subtotal": 2000.0,
        "discount": 0.0,
        "tax": 360.0,
        "final_total": 2360.0,
        "shipping_method": "Express Metro Courier",
        "tracking_id": "TRK-HIST204",
        "decision": "DISPATCHED",
        "hold_reason": None,
        "execution_mode": "SEED",
        "product_id": "P101",
        "product_name": "Wireless Headphones",
        "quantity": 1,
        "unit_price": 2000.0,
        "created_at": "2026-10-18T10:20:00Z",
    },
    # C103: Repeated cancelled orders (3 cancellations -> +20 risk)
    {
        "order_id": "ORD-HIST-301",
        "customer_id": "C103",
        "customer_name": "Rohan Verma",
        "address": "77 Sector 18, Noida, Uttar Pradesh 201301",
        "payment_status": "PAID",
        "validation_status": "VALID",
        "inventory_status": "RESERVED",
        "fraud_status": "LOW",
        "pricing_status": "PRICED",
        "dispatch_status": "NOT_DISPATCHED",
        "fraud_score": 10,
        "subtotal": 1500.0,
        "discount": 0.0,
        "tax": 270.0,
        "final_total": 1770.0,
        "shipping_method": None,
        "tracking_id": None,
        "decision": "CANCELLED",
        "hold_reason": "Customer cancelled after confirmation",
        "execution_mode": "SEED",
        "product_id": "P103",
        "product_name": "Bluetooth Speaker",
        "quantity": 1,
        "unit_price": 1500.0,
        "created_at": "2026-10-01T08:00:00Z",
    },
    {
        "order_id": "ORD-HIST-302",
        "customer_id": "C103",
        "customer_name": "Rohan Verma",
        "address": "77 Sector 18, Noida, Uttar Pradesh 201301",
        "payment_status": "PAID",
        "validation_status": "VALID",
        "inventory_status": "RESERVED",
        "fraud_status": "LOW",
        "pricing_status": "PRICED",
        "dispatch_status": "NOT_DISPATCHED",
        "fraud_score": 15,
        "subtotal": 2000.0,
        "discount": 0.0,
        "tax": 360.0,
        "final_total": 2360.0,
        "shipping_method": None,
        "tracking_id": None,
        "decision": "CANCELLED",
        "hold_reason": "Customer cancelled after confirmation",
        "execution_mode": "SEED",
        "product_id": "P101",
        "product_name": "Wireless Headphones",
        "quantity": 1,
        "unit_price": 2000.0,
        "created_at": "2026-10-12T12:15:00Z",
    },
    {
        "order_id": "ORD-HIST-303",
        "customer_id": "C103",
        "customer_name": "Rohan Verma",
        "address": "77 Sector 18, Noida, Uttar Pradesh 201301",
        "payment_status": "PAID",
        "validation_status": "VALID",
        "inventory_status": "RESERVED",
        "fraud_status": "LOW",
        "pricing_status": "PRICED",
        "dispatch_status": "NOT_DISPATCHED",
        "fraud_score": 20,
        "subtotal": 1200.0,
        "discount": 0.0,
        "tax": 216.0,
        "final_total": 1416.0,
        "shipping_method": None,
        "tracking_id": None,
        "decision": "CANCELLED",
        "hold_reason": "Customer cancelled before dispatch",
        "execution_mode": "SEED",
        "product_id": "P105",
        "product_name": "Keyboard",
        "quantity": 1,
        "unit_price": 1200.0,
        "created_at": "2026-10-25T17:40:00Z",
    },
    # C104: High-risk customer (3 failed payments + prior fraud flag -> >= 60 HIGH)
    {
        "order_id": "ORD-HIST-401",
        "customer_id": "C104",
        "customer_name": "Vikram Mehta",
        "address": "901 Linking Road, Mumbai, Maharashtra 400050",
        "payment_status": "FAILED",
        "validation_status": "INVALID",
        "inventory_status": "PENDING",
        "fraud_status": "HIGH",
        "pricing_status": "SKIPPED",
        "dispatch_status": "NOT_DISPATCHED",
        "fraud_score": 65,
        "subtotal": 7000.0,
        "discount": 0.0,
        "tax": 0.0,
        "final_total": 0.0,
        "shipping_method": None,
        "tracking_id": None,
        "decision": "REJECTED",
        "hold_reason": "Payment authorization failed",
        "execution_mode": "SEED",
        "product_id": "P102",
        "product_name": "Smart Watch",
        "quantity": 2,
        "unit_price": 3500.0,
        "created_at": "2026-10-14T20:10:00Z",
    },
    {
        "order_id": "ORD-HIST-402",
        "customer_id": "C104",
        "customer_name": "Vikram Mehta",
        "address": "901 Linking Road, Mumbai, Maharashtra 400050",
        "payment_status": "FAILED",
        "validation_status": "INVALID",
        "inventory_status": "PENDING",
        "fraud_status": "HIGH",
        "pricing_status": "SKIPPED",
        "dispatch_status": "NOT_DISPATCHED",
        "fraud_score": 70,
        "subtotal": 6000.0,
        "discount": 0.0,
        "tax": 0.0,
        "final_total": 0.0,
        "shipping_method": None,
        "tracking_id": None,
        "decision": "REJECTED",
        "hold_reason": "Payment authorization failed",
        "execution_mode": "SEED",
        "product_id": "P101",
        "product_name": "Wireless Headphones",
        "quantity": 3,
        "unit_price": 2000.0,
        "created_at": "2026-10-19T21:05:00Z",
    },
    {
        "order_id": "ORD-HIST-403",
        "customer_id": "C104",
        "customer_name": "Vikram Mehta",
        "address": "901 Linking Road, Mumbai, Maharashtra 400050",
        "payment_status": "UNPAID",
        "validation_status": "INVALID",
        "inventory_status": "PENDING",
        "fraud_status": "HIGH",
        "pricing_status": "SKIPPED",
        "dispatch_status": "NOT_DISPATCHED",
        "fraud_score": 75,
        "subtotal": 3500.0,
        "discount": 0.0,
        "tax": 0.0,
        "final_total": 0.0,
        "shipping_method": None,
        "tracking_id": None,
        "decision": "HELD_FOR_REVIEW",
        "hold_reason": "Repeated failed payments and suspicious order pattern",
        "execution_mode": "SEED",
        "product_id": "P102",
        "product_name": "Smart Watch",
        "quantity": 1,
        "unit_price": 3500.0,
        "created_at": "2026-10-28T22:15:00Z",
    },
    # C105: Brand-new customer (0 prior orders)
]

DEFAULT_FRAUD_FLAGS = [
    (
        "C104",
        "ORD-HIST-403",
        "Prior chargeback alert and multiple failed card attempts",
        75,
        "2026-10-28T22:15:30Z",
    ),
]


class DatabaseManager:
    """Transactional SQLite wrapper for catalog, orders, and customer fraud memory."""

    def __init__(self, db_path: Path | str, products_json_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.products_json_path = Path(products_json_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_and_seed()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL CHECK(stock >= 0),
                category TEXT,
                substitute_id TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE,
                customer_id TEXT NOT NULL,
                customer_name TEXT,
                customer_phone TEXT DEFAULT '',
                address TEXT,
                payment_status TEXT,
                validation_status TEXT,
                inventory_status TEXT,
                fraud_status TEXT,
                pricing_status TEXT,
                dispatch_status TEXT,
                fraud_score INTEGER DEFAULT 0,
                subtotal REAL DEFAULT 0.0,
                discount REAL DEFAULT 0.0,
                tax REAL DEFAULT 0.0,
                final_total REAL DEFAULT 0.0,
                shipping_method TEXT,
                tracking_id TEXT,
                expected_delivery_date TEXT,
                delivery_eta_window TEXT,
                decision TEXT NOT NULL,
                hold_reason TEXT,
                execution_mode TEXT DEFAULT 'DEMO',
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS fraud_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                fraud_score INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS restock_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                product_name TEXT,
                customer_name TEXT DEFAULT 'Storefront Visitor',
                customer_contact TEXT DEFAULT '',
                status TEXT DEFAULT 'OPEN',
                created_at TEXT NOT NULL
            );
            """
        )

    def _seed_defaults(self, conn: sqlite3.Connection) -> None:
        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            raw = json.loads(self.products_json_path.read_text(encoding="utf-8"))
            for item in raw.get("products", []):
                conn.execute(
                    """
                    INSERT INTO products (product_id, name, price, stock, category, substitute_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["product_id"],
                        item["name"],
                        float(item["price"]),
                        int(item["stock"]),
                        item.get("category", "General"),
                        item.get("substitute_id"),
                    ),
                )

        customer_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if customer_count == 0:
            now = utc_now_iso()
            for cid, name, email in DEFAULT_CUSTOMERS:
                conn.execute(
                    "INSERT INTO customers (customer_id, name, email, created_at) VALUES (?, ?, ?, ?)",
                    (cid, name, email, now),
                )

        order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if order_count == 0:
            for row in DEFAULT_HISTORICAL_ORDERS:
                conn.execute(
                    """
                    INSERT INTO orders (
                        order_id, idempotency_key, customer_id, customer_name, address,
                        payment_status, validation_status, inventory_status, fraud_status,
                        pricing_status, dispatch_status, fraud_score, subtotal, discount,
                        tax, final_total, shipping_method, tracking_id, decision,
                        hold_reason, execution_mode, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["order_id"],
                        f"seed-{row['order_id']}",
                        row["customer_id"],
                        row["customer_name"],
                        row["address"],
                        row["payment_status"],
                        row["validation_status"],
                        row["inventory_status"],
                        row["fraud_status"],
                        row["pricing_status"],
                        row["dispatch_status"],
                        row["fraud_score"],
                        row["subtotal"],
                        row["discount"],
                        row["tax"],
                        row["final_total"],
                        row["shipping_method"],
                        row["tracking_id"],
                        row["decision"],
                        row["hold_reason"],
                        row["execution_mode"],
                        row["created_at"],
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row["order_id"],
                        row["product_id"],
                        row["product_name"],
                        row["quantity"],
                        row["unit_price"],
                    ),
                )

        flag_count = conn.execute("SELECT COUNT(*) FROM fraud_flags").fetchone()[0]
        if flag_count == 0:
            for cid, oid, reason, score, ts in DEFAULT_FRAUD_FLAGS:
                conn.execute(
                    """
                    INSERT INTO fraud_flags (customer_id, order_id, reason, fraud_score, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (cid, oid, reason, score, ts),
                )

    def _ensure_migrations(self, conn: sqlite3.Connection) -> None:
        """Add new columns safely to existing SQLite databases without losing data."""
        existing_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(orders)").fetchall()
        }
        migrations = [
            ("customer_phone", "TEXT DEFAULT ''"),
            ("expected_delivery_date", "TEXT"),
            ("delivery_eta_window", "TEXT"),
        ]
        for col, col_def in migrations:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {col} {col_def}")

    def initialize_and_seed(self) -> None:
        """Create schema if missing, apply safe migrations, and seed sample data on first run."""
        with self._connect() as conn:
            self._create_tables(conn)
            self._ensure_migrations(conn)
            self._seed_defaults(conn)

    def reset_demo_data(self) -> None:
        """Wipe and re-seed all tables cleanly for demo reset."""
        with self._connect() as conn:
            conn.executescript(
                """
                DELETE FROM restock_requests;
                DELETE FROM fraud_flags;
                DELETE FROM order_items;
                DELETE FROM orders;
                DELETE FROM products;
                DELETE FROM customers;
                """
            )
            self._seed_defaults(conn)

    # ---- Product & Inventory operations ----

    def list_products(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY product_id").fetchall()
            return [dict(r) for r in rows]

    def get_product(self, product_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
            return dict(row) if row else None

    def reserve_stock(self, product_id: str, quantity: int) -> tuple[bool, int]:
        """Atomically deduct stock if sufficient; never allows negative stock.

        Returns (success, remaining_stock).
        """
        if quantity <= 0:
            prod = self.get_product(product_id)
            return False, int(prod["stock"]) if prod else 0

        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE products SET stock = stock - ? WHERE product_id = ? AND stock >= ?",
                (quantity, product_id, quantity),
            )
            row = conn.execute(
                "SELECT stock FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
            remaining = int(row["stock"]) if row else 0
            return cursor.rowcount == 1, remaining

    def restock_product(self, product_id: str, add_quantity: int) -> int:
        """Add inventory units to a product, resolve open restock requests, and return updated stock."""
        if add_quantity <= 0:
            prod = self.get_product(product_id)
            return int(prod["stock"]) if prod else 0
        with self._connect() as conn:
            conn.execute(
                "UPDATE products SET stock = stock + ? WHERE product_id = ?",
                (int(add_quantity), product_id),
            )
            conn.execute(
                "UPDATE restock_requests SET status = 'FULFILLED' WHERE product_id = ? AND status = 'OPEN'",
                (product_id,),
            )
            row = conn.execute(
                "SELECT stock FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
            return int(row["stock"]) if row else 0

    def create_restock_request(
        self,
        product_id: str,
        customer_name: str = "Storefront Visitor",
        customer_contact: str = "",
    ) -> dict[str, Any]:
        """Record a customer restock request for an out-of-stock product."""
        prod = self.get_product(product_id)
        pname = prod["name"] if prod else product_id
        ts = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO restock_requests (product_id, product_name, customer_name, customer_contact, status, created_at)
                VALUES (?, ?, ?, ?, 'OPEN', ?)
                """,
                (product_id, pname, customer_name.strip() or "Storefront Visitor", customer_contact.strip(), ts),
            )
            return {
                "id": cur.lastrowid,
                "product_id": product_id,
                "product_name": pname,
                "customer_name": customer_name,
                "customer_contact": customer_contact,
                "status": "OPEN",
                "created_at": ts,
            }

    def list_restock_requests(self, status: Optional[str] = "OPEN") -> list[dict[str, Any]]:
        """List customer restock requests (default: OPEN only)."""
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM restock_requests WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM restock_requests ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_open_restock_counts(self) -> dict[str, int]:
        """Return count of OPEN customer restock requests per product_id."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT product_id, COUNT(*) AS cnt FROM restock_requests WHERE status = 'OPEN' GROUP BY product_id"
            ).fetchall()
            return {r["product_id"]: int(r["cnt"]) for r in rows}

    def release_stock(self, product_id: str, quantity: int) -> int:
        """Return previously reserved stock back to available inventory (e.g., on confirmed fraud rejection)."""
        return self.restock_product(product_id, quantity)

    def get_substitute_product(self, product_id: str) -> Optional[dict[str, Any]]:
        """Find an in-stock substitute product (configured substitute first, else same category)."""
        with self._connect() as conn:
            current = conn.execute(
                "SELECT * FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
            if not current:
                return None

            sub_id = current["substitute_id"]
            if sub_id:
                sub = conn.execute(
                    "SELECT * FROM products WHERE product_id = ? AND stock > 0", (sub_id,)
                ).fetchone()
                if sub:
                    return dict(sub)

            fallback = conn.execute(
                """
                SELECT * FROM products
                WHERE product_id != ? AND stock > 0
                ORDER BY CASE WHEN category = ? THEN 0 ELSE 1 END, ABS(price - ?) ASC
                LIMIT 1
                """,
                (product_id, current["category"], current["price"]),
            ).fetchone()
            return dict(fallback) if fallback else None

    # ---- Customer & Fraud Memory operations ----

    def ensure_customer(self, customer_id: str, customer_name: str = "") -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
            ).fetchone()
            if existing:
                return dict(existing)

            display_name = customer_name.strip() or f"Customer {customer_id}"
            email = f"{customer_id.lower()}@example.com"
            now = utc_now_iso()
            conn.execute(
                "INSERT INTO customers (customer_id, name, email, created_at) VALUES (?, ?, ?, ?)",
                (customer_id, display_name, email, now),
            )
            return {
                "customer_id": customer_id,
                "name": display_name,
                "email": email,
                "created_at": now,
            }

    def list_customers(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM customers ORDER BY customer_id").fetchall()
            return [dict(r) for r in rows]

    def get_customer_history(
        self, customer_id: str, exclude_order_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Retrieve persistent prior-order and fraud-flag history for a customer."""
        with self._connect() as conn:
            cust = conn.execute(
                "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
            ).fetchone()

            if exclude_order_id:
                orders = conn.execute(
                    """
                    SELECT * FROM orders
                    WHERE customer_id = ? AND order_id != ?
                    ORDER BY created_at DESC
                    """,
                    (customer_id, exclude_order_id),
                ).fetchall()
                flags = conn.execute(
                    """
                    SELECT * FROM fraud_flags
                    WHERE customer_id = ? AND order_id != ?
                    ORDER BY created_at DESC
                    """,
                    (customer_id, exclude_order_id),
                ).fetchall()
            else:
                orders = conn.execute(
                    "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC",
                    (customer_id,),
                ).fetchall()
                flags = conn.execute(
                    "SELECT * FROM fraud_flags WHERE customer_id = ? ORDER BY created_at DESC",
                    (customer_id,),
                ).fetchall()

            order_dicts = [dict(o) for o in orders]
            flag_dicts = [dict(f) for f in flags]

            failed_payments = sum(
                1
                for o in order_dicts
                if str(o.get("payment_status", "")).upper() in {"FAILED", "UNPAID", "DECLINED"}
            )
            cancelled_orders = sum(
                1 for o in order_dicts if str(o.get("decision", "")).upper() == "CANCELLED"
            )
            completed_orders = sum(
                1 for o in order_dicts if str(o.get("decision", "")).upper() == "DISPATCHED"
            )

            return {
                "customer_exists": cust is not None,
                "customer_id": customer_id,
                "customer_name": cust["name"] if cust else "New Customer",
                "total_prior_orders": len(order_dicts),
                "completed_orders": completed_orders,
                "failed_payments": failed_payments,
                "cancelled_orders": cancelled_orders,
                "prior_fraud_flags": len(flag_dicts),
                "prior_fraud_reasons": [f["reason"] for f in flag_dicts],
                "recent_order_ids": [o["order_id"] for o in order_dicts[:5]],
            }

    def record_fraud_flag(
        self, customer_id: str, order_id: str, reason: str, fraud_score: int = 0
    ) -> dict[str, Any]:
        """Persist a fraud flag in SQLite so future orders reflect this history."""
        self.ensure_customer(customer_id)
        ts = utc_now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO fraud_flags (customer_id, order_id, reason, fraud_score, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (customer_id, order_id, reason, fraud_score, ts),
            )
            return {
                "flag_id": cursor.lastrowid,
                "customer_id": customer_id,
                "order_id": order_id,
                "reason": reason,
                "fraud_score": fraud_score,
                "created_at": ts,
            }

    # ---- Order Persistence & Dashboard Queries ----

    def get_order_by_idempotency_key(self, idempotency_key: str) -> Optional[dict[str, Any]]:
        if not idempotency_key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            return dict(row) if row else None

    def save_order(self, state: OrderState) -> None:
        """Persist final OrderState and its items transactionally."""
        self.ensure_customer(state.customer_id, state.customer_name)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orders (
                    order_id, idempotency_key, customer_id, customer_name, customer_phone, address,
                    payment_status, validation_status, inventory_status, fraud_status,
                    pricing_status, dispatch_status, fraud_score, subtotal, discount,
                    tax, final_total, shipping_method, tracking_id,
                    expected_delivery_date, delivery_eta_window, decision,
                    hold_reason, execution_mode, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.order_id,
                    state.idempotency_key or state.order_id,
                    state.customer_id,
                    state.customer_name,
                    state.customer_phone,
                    state.address,
                    state.payment_status,
                    state.validation_status,
                    state.inventory_status,
                    state.fraud_status,
                    state.pricing_status,
                    state.dispatch_status,
                    int(state.fraud_score),
                    float(state.subtotal),
                    float(state.discount),
                    float(state.tax),
                    float(state.final_total),
                    state.shipping_method,
                    state.tracking_id,
                    state.expected_delivery_date,
                    state.delivery_eta_window,
                    state.decision,
                    state.hold_reason,
                    state.execution_mode,
                    state.created_at,
                ),
            )
            conn.execute("DELETE FROM order_items WHERE order_id = ?", (state.order_id,))
            for item in state.items:
                conn.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        state.order_id,
                        item.get("product_id", "UNKNOWN"),
                        item.get("product_name", "Unknown Product"),
                        int(item.get("quantity", 0)),
                        float(item.get("unit_price", 0.0)),
                    ),
                )

    def get_owner_insights(self) -> dict[str, Any]:
        """Compute Owner Intelligence metrics: revenue-at-risk, restock alerts, and customer trust scores."""
        orders = self.list_orders()
        products = self.list_products()
        customers = self.list_customers()

        # 1. Revenue at risk (Shortfalls + Held orders)
        shortfall_orders = [o for o in orders if o["decision"] == "SHORTFALL"]
        held_orders = [o for o in orders if o["decision"] == "HELD_FOR_REVIEW"]
        pending_orders = [o for o in orders if o["decision"] == "PENDING_REVIEW"]
        dispatched_orders = [o for o in orders if o["decision"] == "DISPATCHED"]

        shortfall_loss = round(
            sum(float(o["unit_price"] or 0.0) * int(o["quantity"] or 0) for o in shortfall_orders), 2
        )
        held_value = round(
            sum(
                float(o["subtotal"] or (float(o["unit_price"] or 0.0) * int(o["quantity"] or 0)))
                for o in held_orders
            ),
            2,
        )
        dispatched_revenue = round(sum(float(o["final_total"] or 0.0) for o in dispatched_orders), 2)
        avg_order_value = (
            round(dispatched_revenue / len(dispatched_orders), 2) if dispatched_orders else 0.0
        )
        conversion_rate = (
            round((len(dispatched_orders) / len(orders)) * 100.0, 1) if orders else 0.0
        )

        # 2. Restock recommendations based on low stock + shortfall demand
        shortfall_qty_by_pid: dict[str, int] = {}
        shortfall_rev_by_pid: dict[str, float] = {}
        for o in shortfall_orders:
            pid = o["product_id"]
            qty = int(o["quantity"] or 0)
            shortfall_qty_by_pid[pid] = shortfall_qty_by_pid.get(pid, 0) + qty
            shortfall_rev_by_pid[pid] = shortfall_rev_by_pid.get(pid, 0.0) + (
                float(o["unit_price"] or 0.0) * qty
            )

        open_req_counts = self.get_open_restock_counts()
        restock_alerts: list[dict[str, Any]] = []
        for p in products:
            pid = p["product_id"]
            stock = int(p["stock"])
            missed_qty = shortfall_qty_by_pid.get(pid, 0)
            missed_rev = round(shortfall_rev_by_pid.get(pid, 0.0), 2)
            req_cnt = open_req_counts.get(pid, 0)
            if stock <= 3 or missed_qty > 0 or req_cnt > 0:
                recommended_add = max(10 - stock, missed_qty + req_cnt + 5)
                priority = "CRITICAL" if stock == 0 else ("HIGH" if (missed_qty > 0 or req_cnt > 0) else "WATCH")
                restock_alerts.append(
                    {
                        "product_id": pid,
                        "name": p["name"],
                        "current_stock": stock,
                        "missed_units": missed_qty,
                        "customer_requests": req_cnt,
                        "lost_revenue": missed_rev,
                        "recommended_restock": recommended_add,
                        "priority": priority,
                    }
                )

        # 3. Customer Trust Leaderboard (0-100)
        trust_rows: list[dict[str, Any]] = []
        for c in customers:
            cid = c["customer_id"]
            hist = self.get_customer_history(cid)
            cust_spend = round(
                sum(
                    float(o["final_total"] or 0.0)
                    for o in dispatched_orders
                    if o["customer_id"] == cid
                ),
                2,
            )
            trust_score = 70
            trust_score += min(30, hist["completed_orders"] * 8)
            trust_score -= hist["failed_payments"] * 18
            trust_score -= hist["cancelled_orders"] * 12
            trust_score -= hist["prior_fraud_flags"] * 25
            trust_score = max(0, min(100, trust_score))
            if trust_score >= 80:
                tier = "VIP TRUSTED"
            elif trust_score >= 50:
                tier = "STANDARD"
            else:
                tier = "HIGH-RISK WATCHLIST"
            trust_rows.append(
                {
                    "customer_id": cid,
                    "name": c["name"],
                    "trust_score": trust_score,
                    "tier": tier,
                    "completed_orders": hist["completed_orders"],
                    "failed_payments": hist["failed_payments"],
                    "cancelled_orders": hist["cancelled_orders"],
                    "fraud_flags": hist["prior_fraud_flags"],
                    "lifetime_spend": cust_spend,
                }
            )
        trust_rows.sort(key=lambda r: (-r["trust_score"], -r["lifetime_spend"]))

        return {
            "shortfall_loss": shortfall_loss,
            "held_value": held_value,
            "total_revenue_at_risk": round(shortfall_loss + held_value, 2),
            "pending_count": len(pending_orders),
            "held_count": len(held_orders),
            "dispatched_revenue": dispatched_revenue,
            "avg_order_value": avg_order_value,
            "conversion_rate": conversion_rate,
            "restock_alerts": restock_alerts,
            "customer_trust": trust_rows,
        }

    def list_orders(self) -> list[dict[str, Any]]:
        """Return orders joined with their primary item for UI display."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    o.*,
                    COALESCE(oi.product_id, '-') AS product_id,
                    COALESCE(oi.product_name, '-') AS product_name,
                    COALESCE(oi.quantity, 0) AS quantity,
                    COALESCE(oi.unit_price, 0.0) AS unit_price
                FROM orders o
                LEFT JOIN (
                    SELECT order_id, product_id, product_name, quantity, unit_price
                    FROM order_items
                    GROUP BY order_id
                ) oi ON o.order_id = oi.order_id
                ORDER BY o.created_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_order_details(self, order_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            order = conn.execute(
                "SELECT * FROM orders WHERE order_id = ?", (order_id,)
            ).fetchone()
            if not order:
                return None
            items = conn.execute(
                "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
            ).fetchall()
            flags = conn.execute(
                "SELECT * FROM fraud_flags WHERE order_id = ?", (order_id,)
            ).fetchall()
            result = dict(order)
            result["items"] = [dict(i) for i in items]
            result["fraud_flags"] = [dict(f) for f in flags]
            return result

    def get_dashboard_metrics(self) -> dict[str, Any]:
        """Compute real KPI statistics directly from SQLite orders."""
        orders = self.list_orders()
        total_orders = len(orders)
        dispatched = sum(1 for o in orders if o["decision"] == "DISPATCHED")
        held = sum(1 for o in orders if o["decision"] == "HELD_FOR_REVIEW")
        rejected = sum(
            1 for o in orders if o["decision"] in {"REJECTED", "SHORTFALL", "CANCELLED", "ERROR"}
        )
        total_value = round(
            sum(float(o["final_total"] or 0.0) for o in orders if o["decision"] == "DISPATCHED"),
            2,
        )
        status_counts: dict[str, int] = {}
        for o in orders:
            dec = o["decision"]
            status_counts[dec] = status_counts.get(dec, 0) + 1

        return {
            "total_orders": total_orders,
            "dispatched_orders": dispatched,
            "held_orders": held,
            "rejected_orders": rejected,
            "total_processed_value": total_value,
            "status_counts": status_counts,
        }
