"""
Conftest: stub out app.database before any app module is imported.

SQLAlchemy ORM models (User, PrankSession) inherit from Base.  We supply a
real DeclarativeBase so the ORM mapping resolves correctly without needing
asyncpg or a live database at test time.
"""
import os
import sys
from unittest.mock import MagicMock

from sqlalchemy.orm import DeclarativeBase

# --- Required env vars ---------------------------------------------------
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("MAX_CALL_DURATION_SECONDS", "1")
os.environ.setdefault("TELNYX_API_KEY", "test_key")
os.environ.setdefault("TELNYX_CONNECTION_ID", "test_conn")
os.environ.setdefault("TELNYX_NUMBER", "+15550000000")


# --- Stub app.database ---------------------------------------------------
class _TestBase(DeclarativeBase):
    pass


_db_stub = MagicMock()
_db_stub.Base = _TestBase
_db_stub.SessionLocal = MagicMock()
_db_stub.get_db = MagicMock()
_db_stub.DATABASE_URL = os.environ["DATABASE_URL"]

sys.modules["app.database"] = _db_stub
