# API Changelog

All changes to REST API and Webhook contracts are tracked here, newest first.

## [M2 Release] - 2026-09-30
### Added
- `POST /api/v1/ussd/{secret}` -> Full USSD replay state machine with identity resolution, PIN setup, PIN authentication, 30m lockout, and teacher attendance recording.
- `POST /api/v1/dev/ussd` -> Dev simulator endpoint matching Africa's Talking USSD payload contract.
- `POST /api/v1/webhooks/at/sms-delivery/{secret}` -> Africa's Talking SMS delivery status report webhook updating `sms_outbox` status.
- `GET /api/v1/classes/{class_id}/attendance?date=` -> Returns class attendance submission and student list with absence markers.
- `POST /api/v1/classes/{class_id}/attendance` -> Dashboard manual attendance entry fallback with upsert, absence voiding/creation, and parent SMS queueing.
- `DELETE /api/v1/absences/{id}` -> Voids an absence record, updates submission count, and writes audit log.
- `GET /api/v1/attendance/compliance?school_id=&from=&to=&format=` -> Returns class x day attendance compliance grid (submitted / missing / non_school_day) and supports CSV export (`format=csv`).

## [M1 Release] - 2026-09-30
### Added
- `POST /api/v1/auth/login` -> Authenticates user by email/password, issues JWT access and refresh tokens.
- `POST /api/v1/auth/refresh` -> Issues new access and refresh tokens from valid refresh token.
- `POST /api/v1/auth/logout` -> Logs out user session.
- `GET /api/v1/auth/me` -> Returns current authenticated user profile with masked phone.
- `GET /api/v1/districts`, `POST /api/v1/districts` -> Geography endpoints scoped by user role.
- `GET /api/v1/sectors`, `POST /api/v1/sectors` -> Sector list and admin creation.
- `GET /api/v1/schools`, `POST /api/v1/schools`, `PATCH /api/v1/schools/{id}` -> School management endpoints.
- `GET /api/v1/users`, `POST /api/v1/users`, `PATCH /api/v1/users/{id}`, `POST /api/v1/users/{id}/reset-pin` -> User and USSD staff management.
- `GET /api/v1/schools/{id}/classes`, `POST /api/v1/schools/{id}/classes`, `PATCH /api/v1/classes/{id}` -> Class management.
- `GET /api/v1/students`, `POST /api/v1/students`, `POST /api/v1/students/{id}/guardians` -> Student and guardian management.
- `POST /api/v1/students/import` -> Multipart CSV student import with dry-run support.
- `GET /health` -> `{ "status": "ok", "db": "ok", "version": "0.1.0" }`
- `POST /api/v1/ussd/{secret}` -> Africa's Talking USSD callback endpoint returning `CON Hello Garuka`

