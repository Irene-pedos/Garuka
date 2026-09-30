# GARUKA — Architecture Blueprint & Implementation Plan

## 1. Gaps & Contradictions in SPEC.md (with Proposed Fixes)

### USSD Replay Engine & Idempotency
- **`M_CODE` side-effect during replay (Sec 7.2 vs 7.3):** Spec states replay is pure except commit nodes, but `M_CODE` triggers visit code SMS on a `CON` screen. On subsequent inputs (step n+1), replaying from step 0 would re-trigger OTP SMS on every step.
  - *Fix:* State machine must only trigger intermediate side-effects when `step_index == len(inputs)` (terminal step of current request) AND no unexpired code exists for `(case_id, mentor_id)`. Intermediate replay iterations for `step < n` must execute purely without I/O.
- **PIN re-verification & session race (Sec 7.2 vs 7.3):** Argon2 hashing takes ~50–100ms. Spec says "consume without re-verifying" if `ussd_sessions.authed=true`. If session record is created without locking or missing at step 0, concurrent requests or replay order can cause duplicate hashing or lockouts.
  - *Fix:* At step 0 (`text=""`), insert `ussd_sessions` row (`authed=false`). Verify PIN only on the exact transition where PIN is submitted; set `authed=true` in that transaction. All replay loops skip Argon2 when `authed=true`.
- **Input parsing on trailing/empty delimiters (Sec 7.3):** `text.split("*")` turns `"1*"` or `"1**2"` into empty strings, corrupting `n_inputs` and state transitions.
  - *Fix:* Canonicalize input string before evaluation: strip trailing `*`, reject double asterisks or treat as `S_INVALID`.
- **Idempotency table caching scope (Sec 6 vs 7.3):** `ussd_requests` stores response by `(session_id, n_inputs)`. If user cancels with `00` or navigates back with `0`, `n_inputs` still increments (e.g., `1*0*1`), preventing cache collisions, but cache misses must not re-execute already committed DB mutations.
  - *Fix:* Ensure all write transactions check entity state preconditions (e.g. check if submission already exists before insert).

### Africa's Talking + ngrok Constraints (Sec 3)
- **SMS Quiet Hours blocking real-time OTP (Sec 5 vs 7.2):** `SMS_QUIET_HOURS_START=19:00` would delay `parent_visit_code` until 07:00 next morning if mentor visits in the evening, blocking visit completion.
  - *Fix:* Exempt `parent_visit_code` from quiet hours. Apply quiet hours only to notification templates (`parent_absence`, `parent_case_opened`, `seo_escalation`).
- **Webhook endpoint path mismatch (Sec 3.3 vs 10.2):** Sec 3.3 specifies `POST /api/v1/ussd/{USSD_WEBHOOK_SECRET}`, Sec 10.2 lists `POST /ussd/{secret}`.
  - *Fix:* Standardize on `/api/v1/ussd/{secret}` for USSD and `/api/v1/webhooks/at/sms-delivery/{secret}` for SMS delivery.
- **AT error masking (Sec 3.2):** Telcos and AT terminate sessions on HTTP 4xx/5xx or unhandled exceptions.
  - *Fix:* Wrap the outer webhook handler in a top-level `try/except Exception` that returns HTTP 200 `END Service temporarily unavailable. Please try again.` with header `Content-Type: text/plain; charset=utf-8`.

### Rules Engine (Sec 8)
- **Active Case Duplication:** Spec defines Level 2 triggers but does not specify behavior when an active case (`open`, `mentor_assigned`, `visited`, `escalated_sector`, `escalated_district`) already exists.
  - *Fix:* `evaluate_student` must check for existing active cases. If one exists, update `risk_score` and `last_evaluated_at`, append metrics, but do not open a new case or reassign mentor.
- **Calendar & Data Gap handling:** If a teacher does not submit attendance for 3 days, naive calculation could treat missing days as absences or present.
  - *Fix:* Metrics evaluate only over school days with `attendance_submissions` present for that class. Non-submitted days are flagged as `data_gap` and ignored in consecutive absence streak.
- **SLA Escalation Execution:** Level 3 escalation on missed visit window (`RULE_VISIT_SLA_SCHOOL_DAYS + 2`) cannot happen during absence submission.
  - *Fix:* Evaluated exclusively during nightly cron (00:30 Kigali) by scanning active cases in `mentor_assigned` state with elapsed school days.

### RBAC Scoping & Domain Model (Sec 6 & 10.1)
- **Sector Officer query scope on Cases:** `cases` table has `school_id`, but not `sector_id`. Sector officers have `sector_id`.
  - *Fix:* Query joins `cases -> schools` where `schools.sector_id == current_user.sector_id`. Add composite index on `schools(id, sector_id)`.
- **Visit code hash algorithm:** Spec requires Argon2 for passwords/PINs, but Argon2 for short-lived 4-digit visit codes creates unnecessary CPU load during home visits.
  - *Fix:* Use salted SHA-256 for `visit_codes` (valid 30 min, 3 attempts max). Keep Argon2 for user passwords and staff PINs.
- **Absence voiding cascade:** Voiding an absence via dashboard leaves opened cases orphaned if unaddressed.
  - *Fix:* Voiding sets absence `status='voided'`, recomputes student metrics, and adds an audit log and case event note; it does not delete or auto-close an existing case.

---

## 2. Final Technical Decisions

- **Database / ORM:** SQLAlchemy 2.0 async with `asyncpg`.
  *Rationale:* Native async eliminates thread-pool blocking during bursty Africa's Talking USSD webhook requests requiring <1s SLA.
- **Python Tooling:** `uv` for package management, `ruff` for linting/formatting, `pytest` + `pytest-asyncio` for testing.
  *Rationale:* `uv` offers deterministic, sub-second virtualenv setup; `ruff` and `pytest` deliver maximum CI execution speed.
- **Authentication:** `pwdlib` with `argon2-cffi` for password/PIN hashing; `pyjwt` for JWT signing and decoding.
  *Rationale:* `argon2-cffi` satisfies spec compliance for memory-hard hashes; `pyjwt` is stable, secure, and free of outdated C-extension dependencies.
- **Task Scheduling:** APScheduler 3.x (`AsyncIOScheduler`) run in-process within FastAPI application lifespan.
  *Rationale:* Fulfills the zero-Redis MVP constraint while reliably triggering the 00:30 Kigali nightly rules run and SMS outbox dispatch.
- **Frontend Stack:** Next.js 14+ (App Router), React 18/19, Tailwind CSS v3, TanStack Query v5, Zod v3 + react-hook-form, Recharts v2, next-intl v3.
  *Rationale:* Stable App Router ecosystem with proven TanStack Query client caching and minimal bundle weight for low-bandwidth rural deployments.

---

## 3. Ordered Build Plan per Milestone (M0 to M6)

### Milestone M0: Foundations + Hello-USSD
- [ ] M0.1: Initialize mono-repo structure, `.env.example`, gitignore, and `Makefile` (up, api, test). *Check: `make test` runs pytest.*
- [ ] M0.2: Configure Docker Compose for PostgreSQL 16 and verify connectivity. *Check: `docker compose up` spins up healthy DB.*
- [ ] M0.3: Setup FastAPI app structure with settings (`pydantic-settings`), logging, and `/health`. *Check: `curl /health` returns status ok.*
- [ ] M0.4: Implement `/api/v1/ussd/{secret}` webhook returning static `CON Hello Garuka`. *Check: POST with secret returns 200 `CON Hello Garuka`.*
- [ ] M0.5: Add USSD response length validator (<= 182 chars) and global exception trap. *Check: Raised exception returns 200 `END Service temporarily unavailable...`.*
- [ ] M0.6: Scaffold Next.js app in `apps/web` with Tailwind CSS, layout, and health fetch. *Check: `npm run build` succeeds.*
- [ ] M0.7: Generate typed API client from FastAPI OpenAPI spec (`openapi-typescript`). *Check: Type definitions compile in web app.*

### Milestone M1: Core Data, Auth & Admin REST
- [ ] M1.1: Define SQLAlchemy models for geography (`districts`, `sectors`, `schools`) and migrations. *Check: Alembic upgrade applies cleanly.*
- [ ] M1.2: Define models for users, guardians, classes, students, and calendar (`terms`, `holidays`). *Check: Full schema generated in PostgreSQL.*
- [ ] M1.3: Implement password hashing (Argon2), JWT token generation, and `POST /auth/login`, `/me`. *Check: Login returns valid JWT and user payload.*
- [ ] M1.4: Implement RBAC dependency system enforcing geographic/school scoping per role. *Check: Unit tests confirm 403 when scoping violated.*
- [ ] M1.5: Build CRUD endpoints for schools, sectors, classes, and users with PIN reset. *Check: Head teacher can only list own school's classes.*
- [ ] M1.6: Implement `POST /students/import` CSV handler with dry-run validation. *Check: CSV import inserts students and guardians with row-level error reporting.*
- [ ] M1.7: Write idempotent seed script (`scripts/seed.py`) with sample district, school, users. *Check: Running seed twice yields identical DB state.*
- [ ] M1.8: Build web dashboard login, role-based navigation sidebar, and Users/Schools management. *Check: Admin logs in, views schools, creates user.*
- [ ] M1.9: Build Students list and CSV Import wizard with preview on dashboard. *Check: Uploading valid CSV populates student table in UI.*

### Milestone M2: Teacher USSD, Attendance & SMS Outbox
- [ ] M2.1: Implement USSD identity resolution (phone lookup for staff vs guardian vs both). *Check: Known teacher maps to staff; unknown number ends session.*
- [ ] M2.2: Implement USSD staff PIN setup and verification flow with 3-attempt lockout. *Check: First dial forces setup; wrong PIN 3x locks for 30m.*
- [ ] M2.3: Build stateless USSD replay engine with `0` (back) and `00` (cancel) handling. *Check: Replaying cumulative text navigates correctly across menu tree.*
- [ ] M2.4: Build Teacher flow screens (`T_CLASS`, `T_DATE`, `T_ROLL`, `T_CONFIRM`). *Check: Step-by-step roll number entry correctly accumulates absent students.*
- [ ] M2.5: Implement attendance commit transaction (submission + absence records + voiding). *Check: Saving attendance creates DB records and handles replacements.*
- [ ] M2.6: Implement `sms_outbox` table, `SmsProvider` interface, `ConsoleSmsProvider`, and AT provider. *Check: Console provider logs SMS to stdout in test.*
- [ ] M2.7: Build background SMS outbox worker respecting quiet hours (19:00–07:00 Kigali). *Check: Nighttime SMS delayed until 07:00; dedupe keys prevent double sends.*
- [ ] M2.8: Build dashboard Classes & Attendance compliance grid and manual entry fallback. *Check: Head teacher manually records attendance via UI.*

### Milestone M3: Rules Engine, Cases & Mentor USSD
- [ ] M3.1: Implement calendar service to check school days, terms, and holiday exclusions. *Check: Weekend and holiday dates identified accurately.*
- [ ] M3.2: Build core Rules Engine student evaluation (consecutive days, 30d absences, risk score). *Check: 3 consecutive absences trigger Level 2 case.*
- [ ] M3.3: Implement mentor assignment algorithm (least loaded active mentor in sector). *Check: Case assigned to eligible mentor; falls back to unassigned.*
- [ ] M3.4: Build Mentor USSD menu (`M_CASES`, `M_CASE`, `M_CODE`, `M_OUTCOME`, `M_BARRIER`). *Check: Mentor navigates assigned cases list on USSD.*
- [ ] M3.5: Implement visit code generation and parent SMS dispatch on `M_CODE` arrival. *Check: Code SMS queued for parent; code verified or rejected on USSD.*
- [ ] M3.6: Implement visit outcome commit, case escalation (Level 3), and timeline events. *Check: Mentor submitting `needs_sector_help` escalates case to SEO.*
- [ ] M3.7: Implement APScheduler nightly job (00:30 Kigali) for SLA breach escalation & auto-resolve. *Check: Overdue visit escalates to Level 3; 10-day return resolves case.*
- [ ] M3.8: Build dashboard Cases list (filtered by role), Case detail view, timeline, and mentor assign. *Check: SEO views sector cases and reassigns mentor in UI.*

### Milestone M4: Parent USSD & Help Requests
- [ ] M4.1: Build Parent USSD navigation flow (`P_CHILD`, `P_MENU`, `P_ATT`). *Check: Parent with 2 children picks child and views recent absence count.*
- [ ] M4.2: Build Parent absence explanation flow (`P_ABS_PICK`, `P_REASON`). *Check: Parent selects unexcused date and saves reason code to absence record.*
- [ ] M4.3: Build Parent help request flow (`P_HELP`) creating `help_requests` record. *Check: Submitting barrier creates help request visible to school.*
- [ ] M4.4: Build dashboard Help Requests inbox and status update workflow. *Check: Head teacher marks help request as in_progress.*
- [ ] M4.5: Implement dev-only USSD simulator API `POST /api/v1/dev/ussd`. *Check: Dev endpoint executes replay without AT gateway.*

### Milestone M5: Analytics, Export & Polish
- [ ] M5.1: Build analytics aggregation service (`/analytics/overview`, `/analytics/trends`). *Check: Returns calculated KPIs matching user role scope.*
- [ ] M5.2: Build `/analytics/schools/compare` and `/analytics/mentors` performance endpoints. *Check: SEO compares schools across sector.*
- [ ] M5.3: Implement CSV streaming export for cases, students, absences, and compliance. *Check: `?format=csv` downloads valid CSV file.*
- [ ] M5.4: Build admin settings endpoints (`/settings/thresholds`) reading/writing `app_settings`. *Check: Admin updates absence threshold dynamically.*
- [ ] M5.5: Build dashboard Overview page with KPI cards, Recharts trend lines, and funnel. *Check: Dashboard graphs render live backend metrics.*
- [ ] M5.6: Build Schools Compare and Mentors management dashboard pages. *Check: Sector officer compares school compliance bars.*
- [ ] M5.7: Build Admin UI for thresholds configuration, SMS outbox monitoring, and audit logs. *Check: Admin inspects SMS outbox status and retries failed item.*

### Milestone M6: Hardening, Localization & Pilot Readiness
- [ ] M6.1: Implement rate limiting per IP and phone number on USSD and Auth routes. *Check: 61st request in a minute returns HTTP 429 / USSD limit.*
- [ ] M6.2: Add data retention cleanup jobs (purge `ussd_requests` > 24h, audit retention). *Check: Scheduled cleanup removes stale USSD logs.*
- [ ] M6.3: Implement Kinyarwanda (`rw`) i18n dictionary for USSD screens and SMS templates. *Check: Dialing with `language=rw` renders Kinyarwanda screens.*
- [ ] M6.4: Integrate `next-intl` on frontend with complete English and Kinyarwanda strings. *Check: Language switcher toggles UI locale smoothly.*
- [ ] M6.5: Verify full privacy compliance: sanitize logs (no PIN/raw text), phone masking in UI. *Check: Grepping test logs confirms zero PIN or unhashed phone leaks.*
- [ ] M6.6: End-to-end testing with AT Sandbox simulator via ngrok tunnel. *Check: Full loop verified: Teacher attendance -> SMS -> Case -> Mentor visit.*

---

## 4. Top 10 Highest-Risk Items to Test First

1. **Stateless USSD Replay Determinism:**
   - *How to test:* Unit test simulating cumulative AT strings with back steps (`1*2*0*2`), cancel (`1*00`), and invalid inputs; assert identical resulting screen state and zero state bleed between sessions.
2. **USSD Exception Trapping & 200 OK Guarantee:**
   - *How to test:* Mock unexpected database disconnects, syntax errors, and missing parameters; assert HTTP status is strictly 200, `Content-Type: text/plain`, and body begins with `END Service temporarily unavailable`.
3. **PIN Argon2 Verification & Lockout during Replay:**
   - *How to test:* Test session where PIN is submitted; verify Argon2 runs once, sets `authed=true`, and is skipped on subsequent inputs; verify 3 wrong attempts sets `pin_locked_until` and rejects further dials.
4. **M_CODE Intermediate Side-Effect Isolation:**
   - *How to test:* Advance session to `M_CODE`, assert 1 SMS queued and 1 `visit_code` generated; advance to next step `M_OUTCOME`; verify replay of previous steps does NOT generate a second SMS or duplicate code.
5. **Transactional SMS Quiet Hours Exemption:**
   - *How to test:* Enqueue `parent_visit_code` and `parent_absence` at 20:00 Kigali time; assert `parent_visit_code` is dispatched immediately while `parent_absence` is scheduled for 07:00 next morning.
6. **Attendance Replacement & Absence Voiding:**
   - *How to test:* Teacher submits 3 absent students (A, B, C); teacher replaces same class/day with (A, D); verify B & C are marked `voided`, D is added, and parent SMS is sent only to D (not re-sent to A).
7. **School Calendar & Data-Gap Logic in Rules Engine:**
   - *How to test:* Create absences separated by weekends, official holidays, and unsubmitted school days; verify consecutive streak spans across weekends/holidays but ignores data gaps without triggering false cases.
8. **Case Escalation & Auto-Resolution Lifecycle:**
   - *How to test:* Run mock nightly job on a case with elapsed visit SLA (>5 school days) asserting escalation to Level 3; simulate 10 consecutive attended days asserting transition to `resolved_returned`.
9. **Multi-Tenant RBAC Boundary Enforcement:**
   - *How to test:* Authenticate as Head Teacher A and attempt to query/modify classes or cases of School B; assert strict 403 Forbidden or empty scoped result. Repeat for Sector Officer across sectors.
10. **CSV Student Import Dirty Data & Transaction Rollback:**
    - *How to test:* Post CSV containing 500 valid rows and 1 invalid row (e.g. malformed phone or duplicate roll number) with and without `dry_run=true`; verify error reporting and zero partial database persistence on failure.

---

## 5. Approved Spec Changes

1. **Exempt Real-Time Visit Codes from SMS Quiet Hours (Sec 5 & 8):**
   - *Change:* Update quiet hours policy so transactional visit verification codes (`parent_visit_code`) bypass `SMS_QUIET_HOURS` immediately. Quiet hours apply only to notification messages (`parent_absence`, `parent_case_opened`, `seo_escalation`).
2. **Harmonize USSD & Webhook Path Routing (Sec 3.3 & 10.2):**
   - *Change:* Standardize webhook paths under `/api/v1`: `POST /api/v1/ussd/{secret}` for USSD gateway and `POST /api/v1/webhooks/at/sms-delivery/{secret}` for SMS delivery status callbacks.
3. **Active Case De-duplication Rule (Sec 8):**
   - *Change:* Explicitly mandate that `rules_engine.evaluate_student` will not open a new case if the student already has an active, non-closed case (`open`, `mentor_assigned`, `visited`, `escalated_sector`, `escalated_district`). It updates metrics and risk score only.
4. **Intermediate USSD Side-Effect Restriction (Sec 7.2 & 7.3):**
   - *Change:* Specify that `M_CODE` generates a visit code and sends an SMS if and only if `M_CODE` is the terminal transition of the incoming request (`step_index == len(inputs)`), preventing duplicate SMS dispatch during subsequent replay steps.
