"""MongoDB connection module — replaces SQLAlchemy/PostgreSQL.

Uses PyMongo (sync) so existing route functions keep their `def` signatures.
Falls back to mongomock (in-memory) when the real MongoDB is unreachable,
so the app works for development/demo without an external database.
"""
import os
import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

MONGO_URL = os.environ.get("MONGO_URL", "")
NEON_DATABASE_URL = os.environ.get("NEON_DATABASE_URL", "")
DB_NAME = os.environ.get("DB_NAME", "market_db")
# Only fall back to in-memory mongomock when explicitly allowed (dev/demo mode).
# In production, a bad MONGO_URL must fail fast rather than silently lose data.
_ALLOW_MONGOMOCK = os.environ.get("ALLOW_MONGOMOCK", "false").lower() in ("1", "true", "yes")

_client = None
db: Database = None
USING_MOCK_MONGO = False
USING_NEON_POSTGRES = False


if NEON_DATABASE_URL:
    from postgres_store import PostgresStore

    try:
        _client = PostgresStore(NEON_DATABASE_URL)
        db = _client
        USING_NEON_POSTGRES = True
        logger.info("✅ Connected to Neon PostgreSQL")
    except Exception as exc:
        if not _ALLOW_MONGOMOCK:
            raise
        logger.warning(f"Neon PostgreSQL unavailable ({exc}), using in-memory mongomock")

def _try_real_mongo():
    """Try to connect to the real MongoDB and ping it."""
    if not MONGO_URL:
        raise ValueError("MONGO_URL not set")
    from pymongo import MongoClient

    # Atlas SCRAM users authenticate against the admin database by default.
    # If a generated URI includes the application database in its path but
    # omits authSource, PyMongo may otherwise try to authenticate against that
    # application database and return a misleading "bad auth" error.
    mongo_url = MONGO_URL
    parsed = urlsplit(mongo_url)
    if (
        parsed.scheme == "mongodb+srv"
        and parsed.hostname
        and parsed.hostname.endswith("mongodb.net")
    ):
        options = parse_qsl(parsed.query, keep_blank_values=True)
        if not any(key.lower() == "authsource" for key, _ in options):
            options.append(("authSource", "admin"))
            mongo_url = urlunsplit((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(options),
                parsed.fragment,
            ))

    client = MongoClient(mongo_url, uuidRepresentation="standard", tz_aware=True,
                         serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    # Force a real connection attempt
    client[DB_NAME].command("ping")
    return client

def _use_mock_mongo():
    """Fall back to mongomock (in-memory) database."""
    global USING_MOCK_MONGO
    USING_MOCK_MONGO = True
    import mongomock
    logger.warning("⚠️  Using in-memory mongomock — data will NOT persist across restarts")
    client = mongomock.MongoClient(uuidRepresentation="standard", tz_aware=True)
    return client

if not USING_NEON_POSTGRES:
    try:
        _client = _try_real_mongo()
        logger.info("✅ Connected to real MongoDB")
    except Exception as exc:
        if _ALLOW_MONGOMOCK:
            logger.warning(f"Real MongoDB unavailable ({exc}), falling back to in-memory mongomock")
            _client = _use_mock_mongo()
        else:
            logger.error(
                f"MongoDB connection failed: {exc}. "
                "Set ALLOW_MONGOMOCK=true to use in-memory fallback in dev/demo mode."
            )
            raise

if not USING_NEON_POSTGRES:
    db = _client[DB_NAME]

DB_BACKEND = "neon-postgres" if USING_NEON_POSTGRES else ("mongomock" if USING_MOCK_MONGO else "mongodb")


def get_db() -> Database:
    """FastAPI dependency that yields the MongoDB database handle."""
    return db


def get_client():
    return _client


# ────────────── Collection name constants ──────────────
class C:
    users = "users"
    settings = "settings"
    categories = "categories"
    products = "products"
    barcodes = "barcodes"
    product_batches = "product_batches"
    customers = "customers"
    suppliers = "suppliers"
    customer_accounts = "customer_accounts"
    supplier_accounts = "supplier_accounts"
    customer_payments = "customer_payments"
    supplier_payments = "supplier_payments"
    shifts = "shifts"
    sales = "sales"
    sale_items = "sale_items"
    sale_payments = "sale_payments"
    sale_returns = "sale_returns"
    sale_return_items = "sale_return_items"
    purchases = "purchases"
    purchase_items = "purchase_items"
    supplier_returns = "supplier_returns"
    supplier_return_items = "supplier_return_items"
    inventory_movements = "inventory_movements"
    stock_audits = "stock_audits"
    stock_audit_items = "stock_audit_items"
    expenses = "expenses"
    expense_categories = "expense_categories"
    audit_logs = "audit_logs"
    notifications = "notifications"
    devices = "devices"
    sync_queue = "sync_queue"
    product_change_requests = "product_change_requests"
    day_closes = "day_closes"


def init_indexes():
    """Create indexes for fast queries. Idempotent."""
    try:
        db[C.users].create_index([("username", ASCENDING)], unique=True)
        db[C.users].create_index([("email", ASCENDING)], unique=True)
        db[C.users].create_index([("role", ASCENDING)])
        db[C.settings].create_index([("key", ASCENDING)], unique=True)
        db[C.products].create_index([("sku", ASCENDING)], unique=True, sparse=True)
        db[C.products].create_index([("name", ASCENDING)])
        db[C.products].create_index([("is_featured", ASCENDING), ("featured_order", ASCENDING)])
        db[C.products].create_index([("expiry_date", ASCENDING)])
        db[C.categories].create_index([("name", ASCENDING)], unique=True)
        db[C.barcodes].create_index([("barcode", ASCENDING)], unique=True)
        db[C.barcodes].create_index([("product_id", ASCENDING)])
        db[C.customers].create_index([("phone", ASCENDING)])
        db[C.suppliers].create_index([("name", ASCENDING)])
        db[C.sales].create_index([("sale_number", ASCENDING)], unique=True, sparse=True)
        db[C.sales].create_index([("created_at", DESCENDING)])
        db[C.sale_items].create_index([("sale_id", ASCENDING)])
        db[C.expense_categories].create_index([("name", ASCENDING)], unique=True)
        db[C.expenses].create_index([("created_at", DESCENDING)])
        db[C.audit_logs].create_index([("created_at", DESCENDING)])
        db[C.notifications].create_index([("user_id", ASCENDING), ("read", ASCENDING)])
        db[C.day_closes].create_index([("close_date", ASCENDING)], unique=True)
    except Exception as e:
        logger.warning(f"Index creation skipped: {e}")
