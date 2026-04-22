"""
reset_db.py — Drop and recreate all database tables.

Usage (standalone / pre-deploy command):
    python reset_db.py

This script imports the SQLAlchemy engine and Base from app.database /
app.models, drops every table defined in the ORM metadata, then recreates
them from scratch.  It is intentionally destructive — all data will be lost.

Typical Railway usage:
    Set as a pre-deploy command in railway.toml:

        [deploy]
        preDeployCommand = "python reset_db.py"

    Or run it once via the Railway CLI:
        railway run python reset_db.py
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Import models first so that all ORM classes register themselves on Base.metadata
# before we call drop_all / create_all.
from app import models  # noqa: F401  (side-effect import)
from app.database import engine, Base


def reset_database() -> None:
    logger.info("Starting database reset…")

    logger.info("Dropping all tables: %s", list(Base.metadata.tables.keys()))
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped successfully.")

    logger.info("Recreating all tables…")
    Base.metadata.create_all(bind=engine)
    logger.info(
        "All tables recreated successfully: %s",
        list(Base.metadata.tables.keys()),
    )

    logger.info("Database reset complete.")


if __name__ == "__main__":
    reset_database()
