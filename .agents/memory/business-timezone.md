---
name: Business timezone
description: The timezone boundary used by sales, reports, dashboard KPIs, and day closing
---

Accounting dates must be calculated in `Asia/Aden` by default, then converted to UTC for database ranges. Stored timestamps remain UTC.

**Why:** A sale after midnight in Yemen was previously classified under the previous UTC date, which could place it in the wrong daily report and cash close.

**How to apply:** Use the shared business-time helpers for local today, day ranges, month ranges, invoice numbering, expiry checks, and day-close/report defaults. Override with `BUSINESS_TIMEZONE` only when the store operates elsewhere.