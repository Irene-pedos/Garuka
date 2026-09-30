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

## Milestone M3: Rules Engine, Cases, Mentors & Scheduler
- [x] M3.1: Implement risk score algorithm (grade weight, repeater, overage, 30d absences, prior cases).
- [x] M3.2: Implement least-loaded mentor assignment in student's sector (cap 15 active cases).
- [x] M3.3: Implement trigger evaluator (3 consecutive absences, 5 in 30 days) and case event audit logging.
- [x] M3.4: Implement Mentor USSD flow (`M_MENU`, `M_CASES` sorted by SLA, `M_CASE_DETAIL`).
- [x] M3.5: Implement visit code generation (salted SHA-256), parent SMS dispatch, 3-attempt lock, 0=unverified.
- [x] M3.6: Implement mentor outcome flow (`M_OUTCOME`, `M_BARRIER`) and atomic commit transaction with Level 3 escalation.
- [x] M3.7: Implement background APScheduler running `run_nightly_rules` at 00:30 Africa/Kigali and SMS outbox dispatch.
- [x] M3.8: Build Cases & Mentors REST endpoints (`GET /cases`, `GET /cases/{id}`, `PATCH /cases/{id}/assign`, `POST /cases/{id}/escalate`, `POST /cases/{id}/notes`, `POST /cases/{id}/resolve`, `GET /mentors`).
- [x] M3.9: Build web dashboard Cases list with filters, Case Detail view (metrics, heatmap, visits, audit timeline, action modals), and Mentors directory.

### Current State
- **Done:** Milestone M0, Milestone M1, Milestone M2, and Milestone M3 complete!
  - Rules Engine: automatic case opening on 3 consecutive absences or 5 monthly absences, risk scoring (0-100), least-loaded mentor assignment.
  - Nightly APScheduler: running at 00:30 Africa/Kigali for SLA breach escalation (Level 3 SEO after SLA school days), Level 4 district escalation (>=14 days), and 10-day return streak auto-resolution.
  - Background SMS outbox dispatcher running every 30 seconds.
  - Mentor USSD workflow: oldest SLA first case listing, case details, OTP visit code generation, SMS dispatch to parent, 3-attempt locking, unverified fallback, outcome and barrier recording, and atomic visit commit.
  - Cases & Mentors REST endpoints with strict role-based access control (Head Teacher, Sector Officer, District Director, Admin).
  - Web Dashboard: Cases directory with search and level/status filtering, Case Detail view with 4 metrics, attendance heatmap, visits list, audit timeline, and actions (assign mentor, escalate, note, resolve), and Mentors workload table.
  - All 33 automated tests passing (`uv run pytest -v`).
  - Next.js Turbopack build verified cleanly (`npm run build`).
- **In Progress:** Milestone M3 complete, ready for Milestone M4.
- **Next:** Milestone M4: Guardian USSD, Help Requests & SMS Follow-up.

