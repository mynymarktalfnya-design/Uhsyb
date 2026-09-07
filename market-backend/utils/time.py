"""Business-time helpers for accounting reports and daily operations."""
import os
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def _load_business_timezone() -> ZoneInfo:
    name = os.environ.get("BUSINESS_TIMEZONE", "Asia/Aden")
    try:
        return ZoneInfo(name)
    except Exception:
        # Keep the server usable if an invalid optional setting is supplied.
        return ZoneInfo("Asia/Aden")


BUSINESS_TIMEZONE = _load_business_timezone()


def business_now() -> datetime:
    return datetime.now(BUSINESS_TIMEZONE)


def business_today() -> date:
    return business_now().date()


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def day_range_utc(target: date) -> tuple[datetime, datetime]:
    """Return the UTC half-open range covering one local business day."""
    start_local = datetime.combine(target, time.min, tzinfo=BUSINESS_TIMEZONE)
    end_local = start_local + timedelta(days=1)
    return _as_utc(start_local), _as_utc(end_local)


def month_range_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """Return the UTC half-open range covering one local business month."""
    start_local = datetime(year, month, 1, tzinfo=BUSINESS_TIMEZONE)
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=BUSINESS_TIMEZONE)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=BUSINESS_TIMEZONE)
    return _as_utc(start_local), _as_utc(end_local)


def year_range_utc(year: int) -> tuple[datetime, datetime]:
    return month_range_utc(year, 1)[0], month_range_utc(year + 1, 1)[0]
