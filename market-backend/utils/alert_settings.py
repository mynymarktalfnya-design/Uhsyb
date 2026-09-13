"""Shared inventory alert settings."""
from database import C

ALERT_SETTINGS_KEY = "inventory_alerts"
DEFAULT_EXPIRY_ALERT_DAYS = 30
DEFAULT_LOW_STOCK_THRESHOLD = 0.0


def get_alert_settings(db) -> dict:
    row = db[C.settings].find_one({"key": ALERT_SETTINGS_KEY})
    value = row.get("value", {}) if row else {}
    if not isinstance(value, dict):
        value = {}

    try:
        expiry_days = int(value.get("expiry_alert_days", DEFAULT_EXPIRY_ALERT_DAYS))
    except (TypeError, ValueError):
        expiry_days = DEFAULT_EXPIRY_ALERT_DAYS
    try:
        low_stock = float(value.get("low_stock_threshold", DEFAULT_LOW_STOCK_THRESHOLD))
    except (TypeError, ValueError):
        low_stock = DEFAULT_LOW_STOCK_THRESHOLD

    return {
        "expiry_alert_days": max(1, min(365, expiry_days)),
        "low_stock_threshold": max(0.0, min(100000.0, low_stock)),
    }