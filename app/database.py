from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

# ---------------------------------------------------------------------------
# Resolve DATABASE_URL
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    logger.error(
        "DATABASE_URL environment variable is not set. "
        "Make sure the Postgres service is linked and the reference variable "
        "${{ Postgres.DATABASE_URL }} is configured correctly."
    )
    raise RuntimeError("DATABASE_URL environment variable is not set.")

# Railway (and some other providers) may supply a 'postgres://' scheme, but
# SQLAlchemy 1.4+ requires 'postgresql://'.  Fix it transparently.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    logger.info("DATABASE_URL scheme normalised from 'postgres://' to 'postgresql://'.")

# Log a masked version of the URL so we can confirm it was received correctly
# without leaking credentials into the logs.
try:
    from urllib.parse import urlparse, urlunparse
    _parsed = urlparse(DATABASE_URL)
    _masked = urlunparse(_parsed._replace(
        netloc=f"****:****@{_parsed.hostname}:{_parsed.port}"
    ))
    logger.info("Connecting to database: %s", _masked)
except Exception:
    logger.info("DATABASE_URL is set (could not parse for masking).")

# ---------------------------------------------------------------------------
# Engine creation
# ---------------------------------------------------------------------------
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # verify connections before use; avoids stale-conn errors
        pool_recycle=300,     # recycle connections every 5 min to avoid server-side timeouts
    )
    logger.info("SQLAlchemy engine created successfully.")
except Exception as exc:
    logger.error(
        "Failed to create SQLAlchemy engine. "
        "Check that DATABASE_URL is a valid PostgreSQL connection string. "
        "Error: %s",
        exc,
    )
    raise RuntimeError(f"Database engine creation failed: {exc}") from exc

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ---------------------------------------------------------------------------
# Startup connectivity check
# ---------------------------------------------------------------------------
def check_database_connection() -> None:
    """
    Attempt a lightweight query against the database.
    Logs a clear error and raises RuntimeError if the connection cannot be
    established, so the app fails fast with a useful message instead of a
    silent 502.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully.")
    except Exception as exc:
        logger.error(
            "Cannot reach the database. "
            "Verify that the Postgres service is running and that "
            "DATABASE_URL points to the correct host/port/credentials. "
            "Error: %s",
            exc,
        )
        raise RuntimeError(f"Database connection check failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Dependency to get DB session
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
