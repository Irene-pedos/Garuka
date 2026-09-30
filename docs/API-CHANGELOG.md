# API Changelog

All changes to REST API and Webhook contracts are tracked here, newest first.

## [M3 Release] - 2026-09-30
### Added
- `GET /api/v1/cases` -> Returns role-scoped case list with filters (`status`, `level`, `school_id`, `sector_id`, `mentor_id`, `q`).
- `GET /api/v1/cases/{id}` -> Returns comprehensive case file including metrics, 30-day absence heatmap, mentor home visits, and audit timeline.
- `PATCH /api/v1/cases/{id}/assign` -> Reassigns mentor to case, transitions status to `mentor_assigned`, and logs audit event.
- `POST /api/v1/cases/{id}/escalate` -> Escalates case to Level 3 (`escalated_sector`) with contextual note.
- `POST /api/v1/cases/{id}/notes` -> Appends audit note to case timeline.
- `POST /api/v1/cases/{id}/resolve` -> Resolves/closes case (`resolved_returned`, `closed_moved`, `closed_other`) with timestamp.
- `GET /api/v1/mentors` -> Returns community mentors list with workload (active cases), 30-day visit count, and OTP verification percentage.
- `POST /api/v1/ussd/{secret}` -> Added Mentor USSD journey (`M_MENU`, `M_CASES`, `M_CASE_DETAIL`, `M_CODE`, `M_OUTCOME`, `M_BARRIER`) with parent OTP code dispatch and verification.

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

