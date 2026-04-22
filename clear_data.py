"""
clear_data.py
-------------
Truncates all application tables in the correct foreign-key order, leaving
the schema (columns, constraints, indexes) completely intact.

Usage:
    python clear_data.py
    railway run python clear_data.py
"""

from sqlalchemy import text
from app.database import engine

# Tables listed leaf-first so that every child row is removed before its
# parent, satisfying all foreign-key constraints without disabling them.
TABLES = [
    "order_items",
    "order_history",
    "bills",
    "orders",
    "reservations",
    "item_requests",
    "menu_items",
    "tables",
    "floors",
    "users",
    "cafes",
    "token_blocklist",
]


def clear_all_tables() -> None:
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            print(f"✓ Cleared: {table}")

    print("\nAll tables cleared successfully.")


if __name__ == "__main__":
    clear_all_tables()
