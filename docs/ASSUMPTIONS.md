# Engineering Assumptions Log

This document records architectural, technical, and operational assumptions made during development when resolving ambiguities in `docs/SPEC.md`.

## Milestone M0
1. **Python Environment:** Python 3.12+ (or 3.14 on host) managed with `uv`. Dependencies pinned in `apps/api/pyproject.toml`.
2. **Database Engine:** Async SQLAlchemy 2.0 with `asyncpg` for production/dev; PostgreSQL 16 is running as a service on localhost:5432.
3. **AT Webhook Paths:** Both `/api/v1/ussd/{secret}` and `/api/v1/webhooks/at/sms-delivery/{secret}` use standard path segments matching Section 10.2.
4. **USSD Character Limits:** The hard cap is 182 characters per AT specifications, with target <= 160 characters for standard single-frame USSD.
5. **No Raw Text / No PIN Logging:** All loggers strip or mask raw incoming `text` and avoid storing plain PIN digits in any log stream or database table.
