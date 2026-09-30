# API Changelog

All changes to REST API and Webhook contracts are tracked here, newest first.

## [Unreleased] - 2026-09-30
### Added
- `GET /health` -> `{ "status": "ok", "db": "ok", "version": "0.1.0" }`
- `POST /api/v1/ussd/{secret}` -> Africa's Talking USSD callback endpoint returning `CON Hello Garuka`
