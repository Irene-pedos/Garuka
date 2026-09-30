# API Changelog

All changes to REST API and Webhook contracts are tracked here, newest first.

## [Unreleased] - 2026-09-30
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
