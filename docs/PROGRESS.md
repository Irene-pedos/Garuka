# Project Progress Tracker

## Milestone M0: Foundations + Hello-USSD
- [x] M0.1: Initialize mono-repo structure, `.env.example`, gitignore, and Makefile.
- [x] M0.2: Database connectivity and configuration (PostgreSQL 16 on port 5433).
- [x] M0.3: FastAPI core setup with settings, logging (no-PIN/raw text rule), and `/health` route.
- [x] M0.4: `/api/v1/ussd/{secret}` webhook returning `CON Hello Garuka`.
- [x] M0.5: USSD response validation (<= 182 chars) and global exception handling.
- [x] M0.6: Next.js frontend scaffold in `apps/web` with shadcn preset (`b69EkWqpAe`).
- [x] M0.7: OpenAPI typed client generation via `openapi-typescript`.

## Milestone M1: Core Data, Auth & Admin REST
- [x] M1.1: Define SQLAlchemy models for geography (`districts`, `sectors`, `schools`) and migrations.
- [x] M1.2: Define models for users, guardians, classes, students, and calendar (`terms`, `holidays`).
- [x] M1.3: Implement password hashing (Argon2), JWT token generation, and `POST /auth/login`, `/me`.
- [x] M1.4: Implement RBAC dependency system enforcing geographic/school scoping per role.
- [x] M1.5: Build CRUD endpoints for schools, sectors, classes, and users with PIN reset.
- [x] M1.6: Implement `POST /students/import` CSV handler with dry-run validation.
- [x] M1.7: Write idempotent seed script (`scripts/seed.py`) with sample district, school, users.
- [x] M1.8: Build web dashboard login, role-based navigation sidebar, and Users/Schools management.
- [x] M1.9: Build Students list and CSV Import wizard with preview on dashboard.

## Milestone M2: Teacher USSD, Attendance & SMS Outbox
- [x] M2.1: Implement USSD identity resolution (phone lookup for staff vs guardian vs both).
- [x] M2.2: Implement USSD staff PIN setup and verification flow with 3-attempt lockout.
- [x] M2.3: Build stateless USSD replay engine with `0` (back) and `00` (cancel) handling.
- [x] M2.4: Build Teacher flow screens (`T_CLASS`, `T_DATE`, `T_ROLL`, `T_CONFIRM`).
- [x] M2.5: Implement attendance commit transaction (submission + absence records + voiding).
- [x] M2.6: Implement `sms_outbox` table, `SmsProvider` interface, `ConsoleSmsProvider`, and AT provider.
- [x] M2.7: Build background SMS outbox worker respecting quiet hours (19:00–07:00 Kigali).
- [x] M2.8: Build dashboard Classes & Attendance compliance grid and manual entry fallback.

### Current State
- **Done:** Milestone M0, Milestone M1, and Milestone M2 complete!
  - Teacher USSD replay engine, identity resolution, Argon2 PIN setup/auth with 3-attempt 30m lockout.
  - Teacher attendance USSD screens: single class auto-selection, date choice, roll accumulation, `0` finish, `Bika` confirmation, and atomic commit node.
  - `sms_outbox` with quiet hours (19:00–07:00 Kigali), transactional visit code bypass, deduplication keys, and AT SMS delivery webhook.
  - Attendance REST API: `GET /classes/{id}/attendance`, `POST /classes/{id}/attendance` (dashboard fallback), `DELETE /absences/{id}` (voiding with audit log), and `GET /attendance/compliance` (class x day compliance grid with CSV export).
  - Next.js Dashboard: `/dashboard/attendance` interactive compliance grid (submitted/missing/off) and manual attendance entry & voiding fallback.
  - All 28 automated integration/unit tests passing (`uv run pytest -v`).
  - Next.js Turbopack build verified cleanly (`npm run build`).
- **In Progress:** Ready for Milestone M3 (Rules Engine, Cases & Mentor USSD).
- **Next:** Milestone M3: M3.1 through M3.8.

