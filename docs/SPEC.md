# GARUKA — Development Spec (v0.1)

USSD-based school dropout early-warning and follow-up system for Rwanda.
Working name: **Garuka** ("come back"). This file is the single source of truth for two coding agents, split by token budget:

- **Analyst / architect agent (Codex CLI, limited tokens):** reads this spec **once**, finds gaps and contradictions, and writes `docs/BLUEPRINT.md` (ordered build plan, final technical decisions, task checklists per milestone). It does **not** write application code unless the project lead asks. Keep its output short and precise.
- **Builder agent (agy, larger token budget):** builds **everything** — `apps/api` (FastAPI, PostgreSQL, USSD webhook, SMS, rules engine, REST API) and `apps/web` (Next.js admin dashboard for school heads, sector officers, district directors, admins) — following `docs/BLUEPRINT.md` and this spec.

**Precedence:** if `docs/BLUEPRINT.md` and this file conflict, this file wins, unless the blueprint lists the point under "Approved spec changes" and the project lead has approved it. The builder logs any deviation in `docs/ASSUMPTIONS.md`.

If something here is ambiguous, **do not guess silently**: write the assumption in `docs/ASSUMPTIONS.md` and continue. If the API contract must change, follow section 16.

---

## 0. Read this first (rules for both agents)

1. Everything must work through **Africa's Talking (AT) sandbox** with the backend exposed by **ngrok**. Section 3 is mandatory reading.
2. USSD endpoint **always returns HTTP 200, `Content-Type: text/plain`, body starting with `CON ` or `END `**. Any HTTP error or malformed body makes AT terminate the session. Never let an exception escape the USSD route; catch everything and return `END Service temporarily unavailable. Please try again.`
3. Every USSD screen must be **≤ 160 characters** (hard limit 182). Enforce in the renderer with a unit test.
4. **Never log the raw `text` field or any PIN.** `text` is cumulative and contains the PIN in plain digits on every request.
5. Minors' data: collect the minimum, scope every query by role, write audit logs, never put reasons or diagnoses in SMS.
6. Business dates use **Africa/Kigali (UTC+2)**. Store timestamps as UTC `timestamptz`. Store phone numbers as **E.164** (`+250788123456`).
7. Do not invent AT behavior. If unsure, check https://developers.africastalking.com/docs/ussd/overview and note it in `docs/ASSUMPTIONS.md`.
8. Write tests with the code. A task is not done without tests (section 14).

---

## 1. Product summary

**Problem:** Children in Rwanda drop out of school, especially around the primary-to-secondary transition. Attendance data exists in MINEDUC's SDMS, but the loop from "child absent" to "someone acts" is weak, and rural internet use is low.

**Solution:** Teachers record absences by USSD. Parents get an SMS the same day and can explain the absence by USSD. Repeated absences open a **case**, assigned to a paid local youth **mentor** who visits the home. Barriers the mentor can't solve escalate to the **sector education officer (SEO)**, then the **district director**. Dashboards show cases, trends and reasons.

**Positioning:** Garuka is the *action layer on top of attendance data*, not a replacement for SDMS. MVP imports students by CSV. SDMS API integration is out of scope.

### Actors

| Actor | Channel | Main jobs |
|---|---|---|
| Teacher | USSD (+ dashboard fallback) | Mark absent students each day |
| Parent/guardian | USSD + SMS | Get alerts, explain absences, ask for help |
| Mentor (youth) | USSD | See assigned cases, verify and log home visits |
| Head teacher | Dashboard | See school at-risk list, attendance compliance, notes |
| Sector education officer | Dashboard | Handle escalated cases, manage mentors, compare schools |
| District director | Dashboard | Monitor sector trends and unresolved cases |
| Admin | Dashboard | Users, schools, thresholds, SMS outbox, audit logs |

### MVP scope

In: USSD (teacher, mentor, parent), SMS, rules engine, cases, mentor visit verification, dashboards, CSV student import, RBAC, audit log, en + rw language support.
Out: payments, SDMS API sync, WhatsApp/IVR, predictive ML, French UI (data model supports `fr`, strings optional).

---

## 2. Architecture

```
Phone (any handset)
   │  dials *384*XXXX#  (sandbox)   or the production short code
   ▼
Africa's Talking USSD gateway ──HTTP POST (form-encoded)──► ngrok HTTPS URL
                                                               │
                                                               ▼
                                             FastAPI (localhost:8000)
                                             ├─ /api/v1/ussd/{secret}         (AT webhook)
                                             ├─ /api/v1/webhooks/at/sms-delivery/{secret}
                                             ├─ /api/v1/...                   (REST for dashboard)
                                             ├─ rules engine + scheduler (APScheduler, in-process)
                                             ├─ SMS outbox worker ──► AT SMS API (or console provider)
                                             └─ PostgreSQL
Dashboard (Next.js, localhost:3000) ──HTTPS/JSON + JWT──► FastAPI (CORS allowed)
```

Design choices (keep them):
- **Stateless USSD navigation by replay:** AT sends the *cumulative* `text` (inputs joined by `*`). The engine rebuilds the current screen by replaying all inputs through a pure state machine. Small extra state is stored only for auth and idempotency (section 7.3).
- **Commit nodes END the session.** Database writes happen at terminal screens, so a replayed request never re-runs a write mid-session.
- **SMS via an outbox table** processed by a background loop. Never call the SMS API inside the USSD request path (AT expects a fast response).
- **No Redis in MVP.** PostgreSQL only.

### Tech stack

Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async or sync, pick one and stay consistent), Alembic, PostgreSQL 16, APScheduler, `argon2-cffi`, `python-jose` or `pyjwt`, `httpx`, official `africastalking` Python SDK (or plain `httpx` behind the provider interface), `pytest`, `pytest-asyncio`, `ruff`.
Frontend: Next.js (App Router) + TypeScript + Tailwind CSS, TanStack Query, react-hook-form + zod, Recharts, `next-intl` (en, rw), `openapi-typescript` for a typed client, MSW for mocks.
Infra: Docker Compose for Postgres, ngrok for tunneling.

---

## 3. Africa's Talking + ngrok requirements (mandatory)

### 3.1 What AT sends (USSD callback)

`POST` with `Content-Type: application/x-www-form-urlencoded`:

| Field | Meaning | Example |
|---|---|---|
| `sessionId` | Unique per USSD session | `ATUid_b873edd4e47d269e84e98e571f5e4442` |
| `serviceCode` | Code the user dialed | `*384*78012#` |
| `phoneNumber` | Subscriber MSISDN, international format | `+250780000001` |
| `networkCode` | Telco network code | `99999` in sandbox |
| `text` | Cumulative user inputs joined by `*`. **Empty string on first request** | `""`, `"1"`, `"1*2*5"` |

Parse with FastAPI `Form(...)`. All fields optional-safe (`text` default `""`). Normalize `phoneNumber` to E.164.

### 3.2 What we must return

- `Content-Type: text/plain; charset=utf-8`, HTTP 200.
- Body starts with `CON ` (session continues, expects more input) or `END ` (final screen).
- Newlines inside the body are fine and used for menu formatting.
- A 4xx or a body not starting with CON/END ends the session on AT's side.
- Respond fast (target p95 < 1 s, absolutely under a few seconds). AT may retry on timeout, so handle **duplicate requests idempotently** (section 7.3).

### 3.3 Security of the webhook

AT does not sign USSD callbacks. Protect the endpoint with:
1. **Secret path segment:** `POST /api/v1/ussd/{USSD_WEBHOOK_SECRET}`. Wrong secret → return plain `END Not available.` with 200 (do not reveal a 404 pattern), and log a warning.
2. Rate limit per `phoneNumber` (e.g., 60 requests/minute) and per IP.
3. Optional IP allowlist via env `AT_ALLOWED_IPS` (comma separated; empty = disabled). Get the current AT source IPs from AT's docs/support before enabling; do not hardcode guesses.
4. Never trust `phoneNumber` for anything beyond "a subscriber using this SIM" (SIM-swap risk is accepted for MVP; write actions need a PIN).

### 3.4 SMS

- SDK: `pip install africastalking`; `africastalking.initialize(username, api_key)`; `africastalking.SMS.send(message, [recipients], sender_id=None)`.
- Sandbox username is **always `sandbox`**. Sandbox REST endpoint: `https://api.sandbox.africastalking.com/version1/messaging`. Live: `https://api.africastalking.com/version1/messaging`.
- Sandbox SMS is visible in the AT simulator, not on real phones.
- Sender ID for Rwanda: verify availability and registration with AT. Env `AT_SENDER_ID` may be empty in sandbox.
- Keep SMS ≤ 160 GSM-7 characters (one segment). Avoid accented characters (é, è) since they force UCS-2 (70 chars per segment).
- Implement an `SmsProvider` interface with two implementations: `ConsoleSmsProvider` (prints to logs and marks `sent`, default in dev/tests) and `AfricasTalkingSmsProvider`. Choose via env `SMS_PROVIDER=console|africastalking`.
- Optional delivery-report webhook: `POST /api/v1/webhooks/at/sms-delivery/{secret}` (form fields `id`, `status`, `phoneNumber`, `networkCode`, `failureReason`; verify exact fields against AT docs) → updates `sms_outbox.status`.

### 3.5 Local development loop (exact steps)

1. AT account → switch to **Sandbox** app. Copy sandbox **API key**.
2. Run the API on port 8000 (`uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`).
3. Start ngrok with a **stable domain** so the callback URL doesn't change on every restart (a free ngrok account can reserve one static domain). Example (flag name depends on your ngrok version: `--url` on recent versions, `--domain` on older ones):
   `ngrok http --url=your-name.ngrok-free.app 8000`
4. AT dashboard (Sandbox) → **USSD → Create Channel**:
   - Service code: choose a sandbox code (they look like `*384*NNNN#`).
   - Callback URL: `https://your-name.ngrok-free.app/api/v1/ussd/<USSD_WEBHOOK_SECRET>`
5. AT **Simulator → USSD**: enter a phone number that exists in the seed data (e.g., `+250780000001`), dial the service code.
6. Debug with the **ngrok inspector** at `http://127.0.0.1:4040` (see and replay every AT request). Use **fake PINs** in sandbox since the inspector shows raw `text`.
7. If AT reports errors and the inspector shows an HTML page instead of your response, ngrok's free-tier interstitial is interfering. Check request headers in the inspector, and fall back to a paid/static ngrok plan or another tunnel if needed.

Extra ngrok notes:
- FastAPI runs plain HTTP locally; ngrok terminates HTTPS. Start uvicorn with `--proxy-headers --forwarded-allow-ips="*"` in dev.
- The dashboard can run on `localhost:3000` and call `http://localhost:8000`. Only AT needs the public URL. Configure CORS via `CORS_ORIGINS`.
- Free ngrok tunnels are for development only. Production needs a real host and a dedicated AT USSD code (lead time can be weeks; confirm with AT).

### 3.6 Dev-only simulator endpoint (so nobody is blocked by AT)

`POST /api/v1/dev/ussd` (only when `APP_ENV != production`), JSON `{ "phoneNumber": "+250780000001", "text": "1*2", "sessionId": "dev-1" }` → returns the same plain text the AT route would. The frontend may build an optional "USSD simulator" page on top of it.

---

## 4. Repository layout

```
garuka/
├─ AGENTS.md                    # short rules file (copy section 0 + 3); agy uses its equivalent
├─ docs/
│  ├─ SPEC.md                   # this file
│  ├─ ASSUMPTIONS.md            # agents append here
│  └─ API-CHANGELOG.md          # every contract change, newest first
├─ apps/
│  ├─ api/
│  │  ├─ app/
│  │  │  ├─ main.py
│  │  │  ├─ core/               # config.py, security.py, logging.py, rbac.py
│  │  │  ├─ db/                 # base.py, session.py
│  │  │  ├─ models/             # SQLAlchemy models
│  │  │  ├─ schemas/            # Pydantic models
│  │  │  ├─ api/v1/             # auth, users, geo, classes, students, attendance, cases,
│  │  │  │                      # mentors, help_requests, analytics, settings, sms, audit,
│  │  │  │                      # ussd_webhook, sms_webhook, dev
│  │  │  ├─ services/
│  │  │  │  ├─ ussd/            # engine.py, screens.py, i18n.py, identity.py, render.py
│  │  │  │  ├─ rules_engine.py
│  │  │  │  ├─ cases.py, analytics.py, csv_import.py, audit.py
│  │  │  │  └─ sms/             # provider.py, at_provider.py, console_provider.py, outbox_worker.py
│  │  │  └─ jobs/scheduler.py
│  │  ├─ alembic/  tests/  scripts/seed.py  pyproject.toml  .env.example
│  └─ web/                      # Next.js app (agy)
├─ docker-compose.yml           # postgres (+ optional pgadmin)
└─ Makefile                     # make up | migrate | seed | api | test | tunnel
```

---

## 5. Configuration (`apps/api/.env.example`)

```
APP_ENV=development                 # development|test|production
APP_TZ=Africa/Kigali
DATABASE_URL=postgresql+psycopg://garuka:garuka@localhost:5432/garuka
JWT_SECRET=change-me
JWT_ACCESS_MINUTES=30
JWT_REFRESH_DAYS=7
CORS_ORIGINS=http://localhost:3000

# USSD / Africa's Talking
USSD_WEBHOOK_SECRET=change-me-long-random
USSD_SERVICE_CODE_DISPLAY=*384*1234#       # shown in SMS text; set to your channel code
AT_USERNAME=sandbox
AT_API_KEY=
AT_SENDER_ID=
AT_ALLOWED_IPS=                             # optional allowlist
SMS_PROVIDER=console                        # console|africastalking
SMS_QUIET_HOURS_START=19:00
SMS_QUIET_HOURS_END=07:00
LOG_USSD_PHONE=false                        # if false, store phone hash only in ussd logs

# Rules defaults (also editable in DB app_settings)
RULE_CONSECUTIVE_DAYS=3
RULE_MONTHLY_ABSENCES=5
RULE_ESCALATE_TERM_ABSENCES=10
RULE_VISIT_SLA_SCHOOL_DAYS=3
RULE_RETURN_STREAK_SCHOOL_DAYS=10
RULE_DISTRICT_ESCALATION_DAYS=14
RULE_MAX_BACKDATE_SCHOOL_DAYS=2
MENTOR_MAX_ACTIVE_CASES=15
```

---

## 6. Data model (PostgreSQL)

UUID primary keys (`gen_random_uuid()`), `created_at`/`updated_at` `timestamptz` on all tables. Use Alembic migrations. Column lists below are the contract; add indexes on every FK and on the query columns noted.

### Geography and organization
- `districts(id, name unique)`
- `sectors(id, district_id, name)` unique(district_id, name)
- `schools(id, sector_id, name, code unique nullable, level enum[primary,secondary,both], is_active)`

### People
- `users` — dashboard users and USSD staff (teacher, mentor, etc.)
  `id, role enum[admin,district_director,sector_officer,head_teacher,teacher,mentor], full_name, email unique nullable, phone_e164 unique nullable, password_hash nullable, pin_hash nullable, pin_failed_count int default 0, pin_locked_until nullable, language enum[rw,en,fr] default rw, school_id nullable, sector_id nullable, district_id nullable, is_active bool`
  - Scope rules: teacher/head_teacher → `school_id`; mentor/sector_officer → `sector_id`; district_director → `district_id`; admin → none.
  - Dashboard login needs `email`+`password_hash`. USSD staff need `phone_e164`. A user may have both.
- `guardians(id, full_name, phone_e164 unique, language, consent_at, consent_source enum[school_form,ussd,dashboard], sms_opt_out bool default false)`
- `classes(id, school_id, name, grade int, academic_year int, class_teacher_id nullable)` unique(school_id, name, academic_year)
- `class_teachers(class_id, user_id)` many-to-many (a teacher may teach several classes)
- `students(id, school_id, class_id, student_code nullable unique, roll_number int, full_name, sex enum[F,M] nullable, birth_year int nullable, is_repeater bool default false, status enum[active,transferred,dropped_out,graduated], enrolled_at date)` unique(class_id, roll_number)
  - `student_code` is the SDMS unique student ID when available.
- `student_guardians(student_id, guardian_id, relationship, is_primary)`

### Calendar
- `terms(id, academic_year, term_no, start_date, end_date)` (admin-configured; do not hardcode dates)
- `holidays(id, date unique, name)`
- School day = Monday–Friday and not in `holidays` and inside a term.

### Attendance (exception-based)
- `attendance_submissions(id, class_id, date, submitted_by, source enum[ussd,dashboard], absent_count, submitted_at)` unique(class_id, date)
  A submission means "the teacher recorded this class for the day". Students not listed as absent are implicitly present. No submission = **data gap**, not "present".
- `absences(id, student_id, date, submission_id, status enum[active,voided], reason_code nullable, reason_source enum[parent,teacher,mentor] nullable, reason_at nullable)` unique(student_id, date)

Reason codes: `SICK, WORK, COST, DISTANCE, OTHER` (USSD numbers 1–5 in that order).

### Cases
- `cases(id, ref text unique (e.g. GK-2026-000123), student_id, school_id, status enum[open,mentor_assigned,visited,escalated_sector,escalated_district,resolved_returned,closed_moved,closed_other], level int (2,3,4), trigger enum[consecutive,monthly,term_total,manual], risk_score int, mentor_id nullable, sector_officer_id nullable, opened_at, resolved_at nullable, last_evaluated_at, reopened_count int default 0)` index(status, school_id), index(mentor_id)
- `case_events(id, case_id, type text, actor_user_id nullable, payload jsonb, created_at)` — timeline (opened, assigned, sms_sent, visit_logged, escalated, note, resolved, reopened)
- `mentor_visits(id, case_id, mentor_id, started_at, verified bool, verified_method enum[parent_code,unverified], outcome enum[will_return,plan_agreed,needs_sector_help,moved_away], barrier_code nullable, notes nullable)`
- `visit_codes(id, case_id, mentor_id, code_hash, expires_at, attempts int default 0, used_at nullable)`
- `help_requests(id, student_id, guardian_id, barrier_code, status enum[new,seen,in_progress,closed], created_at)`

Barrier codes: `COST, HUNGER, HEALTH, DISTANCE, FAMILY, OTHER`.

### Messaging, USSD, ops
- `sms_outbox(id, to_e164, template_key, params jsonb, body, dedupe_key unique nullable, status enum[pending,sent,delivered,failed,skipped], provider_message_id nullable, attempts int, last_error nullable, scheduled_at, sent_at nullable, related_student_id nullable, related_case_id nullable)`
- `ussd_sessions(session_id pk, phone_hash, user_id nullable, authed bool default false, created_at, last_seen_at)`
- `ussd_requests(session_id, n_inputs int, screen_key, response_kind, response_body, latency_ms, created_at)` primary key(session_id, n_inputs) — idempotency cache + latency log. Purge after 24 h. **No raw `text` and no PINs stored.**
- `app_settings(key pk, value jsonb, updated_by, updated_at)` — thresholds and toggles
- `audit_logs(id, actor_user_id nullable, actor_role, action, entity_type, entity_id, ip nullable, meta jsonb, created_at)`

---

## 7. USSD specification

### 7.1 Identity and routing (first request, `text == ""`)

1. Normalize `phoneNumber`.
2. Look up `users` (active, with that phone) and `guardians` (with that phone).
3. Routing:
   - Only staff → staff flow. Only guardian → parent flow.
   - Both → `S_ROLE_PICK`.
   - Neither → `END This number is not registered with Garuka. Please contact your school.`
4. Language = user/guardian `language` (default `rw`).

Reserved keys (only where a screen shows them): `0` back or finish (screen says which), `00` cancel to start, `9` next page in lists (max 4 items per page).

### 7.2 Screens (EN text; final copy lives in `services/ussd/i18n.py` keyed by screen)

`{}` are placeholders. Names are shortened to "First L." to fit the limit.

**Common**

| Screen | Body |
|---|---|
| `S_ROLE_PICK` | `CON Garuka\n1. Staff menu\n2. Parent menu` |
| `S_LANG` | `CON Language / Ururimi\n1. Kinyarwanda\n2. English\n3. Francais` → commit → `END Language saved. Dial again.` |
| `S_ERROR` | `END Service temporarily unavailable. Please try again.` |
| `S_INVALID` | Re-show current screen prefixed with `Invalid choice.\n` (stay in session) |

**Staff auth** (all staff roles)

| Screen | Body / logic |
|---|---|
| `T_PIN_SETUP1` (pin_hash is null) | `CON Welcome to Garuka. Create a 4-digit PIN:` |
| `T_PIN_SETUP2` | `CON Repeat your PIN:` → match: save hash, `END PIN saved. Dial again to start.`; mismatch: `END PINs did not match. Dial again.` |
| `T_PIN` | `CON Enter your PIN:` → correct: mark `ussd_sessions.authed=true`, continue. Wrong: increment `pin_failed_count`, `END Wrong PIN. Dial again.` After 3 failures set `pin_locked_until = now+30min` → `END PIN locked. Contact your head teacher.` |

PIN rules: exactly 4 digits, reject `0000`, `1234`, and repeated digits. Hash with argon2. On later requests in the same session, if `authed=true`, **consume the PIN input without re-verifying** (never re-check during replay).

**Teacher menu** (`T_MENU`)

```
CON Garuka
1. Mark absences
2. Today's summary
3. Flagged students
4. Language
```

Mark-absences flow:

| Screen | Body / logic |
|---|---|
| `T_CLASS` (skip if only 1 class) | `CON Select class:\n1. P5 A\n2. P6 B` |
| `T_DATE` | `CON Date:\n1. Today ({dd/mm})\n2. Yesterday ({dd/mm})\n0. Back`. Only offer dates that are school days and within `RULE_MAX_BACKDATE_SCHOOL_DAYS`. |
| `T_ALREADY` (submission exists) | `CON {class} {dd/mm} already saved ({n} absent).\n1. Replace it\n0. Back` |
| `T_ROLL` | `CON Absent: {n} so far.\nEnter roll no. ({min}-{max}).\n0 = finish\n00 = cancel`. After a valid entry prefix `Added {roll} {First L.}.\n`. Invalid: `Roll {x} not found.\n` + screen. Duplicate ignored. |
| `T_CONFIRM` | If n>0: `CON {n} absent: {rolls}.\n1. Save\n2. Cancel` (if >8 rolls show count only). If n==0: `CON No absences: all present?\n1. Yes, save\n2. Cancel` |
| commit | `END Saved. {n} absent in {class} on {dd/mm}. Parents will get an SMS.` |

Commit behavior (single DB transaction): upsert `attendance_submissions`; insert new `absences` (ON CONFLICT DO NOTHING); when replacing, void absences for that class/date not in the new list; enqueue parent SMS **only for newly added absences**; call `rules_engine.evaluate_student` for each new absence (may run in a background task after the response).

`T_SUMMARY`: `END Today {dd/mm}:\nP5A: 3 absent\nP6B: not saved yet`
`T_FLAGGED`: `END Flagged:\nUwase J. P5A L2\nKamana E. P5A L3\n(+2 more on dashboard)`

**Head teacher** may reuse `T_SUMMARY`, `T_FLAGGED`, `S_LANG` (menu: `1. Today's summary 2. Flagged students 3. Language`).

**Mentor menu** (`M_MENU`): `CON Garuka Mentor\n1. My cases\n2. Language`

| Screen | Body / logic |
|---|---|
| `M_CASES` | `CON My cases ({n}):\n1. Uwase J. L2\n2. Kamana E. L3\n9. More` (4 per page, oldest SLA first) |
| `M_CASE` | `CON Uwase J., P5A GS Demo\nAbsent 6 of last 10 days.\nReason: fees\n1. Start visit\n0. Back` |
| `M_CODE` (on "Start visit": generate 4-digit code, SMS to primary guardian, store hash, expires in 30 min) | `CON Code sent to the parent. Enter the 4-digit code the parent shows you.\n0 = no code` |
| `M_OUTCOME` | `CON Visit result:\n1. Child will return\n2. Plan agreed\n3. Needs sector help\n4. Moved away` |
| `M_BARRIER` (if outcome ≠ 1) | `CON Main barrier:\n1. Fees/materials\n2. Hunger\n3. Health\n4. Distance\n5. Family\n6. Other` |
| commit | `END Visit saved. Thank you.` |

Rules: wrong code → `END Wrong code. Start the visit again.` (attempts +1; 3 attempts → 30 min lock on that visit code). `0` (no code) → visit saved with `verified=false` and flagged for SEO spot-check. Outcome `needs_sector_help` → escalate case to level 3. `moved_away` → case pending SEO confirmation (`closed_moved` after SEO confirms on dashboard). `M_CODE` sending the SMS is the **only allowed side effect on a `CON` screen**, made safe by the idempotency cache (7.3).

**Parent menu** (`P_MENU`; if a guardian has >1 child show `P_CHILD` first: `CON Choose child:\n1. Uwase J.\n2. Kamana E.`)

```
CON Garuka - {child}
1. Attendance
2. Explain an absence
3. Ask for help
4. Language
```

| Screen | Body / logic |
|---|---|
| `P_ATT` | `END {child}: {a} absent day(s) in last 30 school days. Last: {dd/mm}.` (or `No absences recently.`) |
| `P_ABS_PICK` | `CON Which day?\n1. {dd/mm}\n2. {dd/mm}\n3. {dd/mm}` (latest 3 active absences without a reason; none → `END No absence needs an explanation.`) |
| `P_REASON` | `CON Reason:\n1. Sick\n2. Farm/house work\n3. Fees/materials\n4. Distance\n5. Other` → `END Thank you. Reason saved.` |
| `P_HELP` | `CON What is the main problem?\n1. Fees/materials\n2. Hunger\n3. Health\n4. Distance\n5. Family\n6. Other` → creates `help_requests` → `END Request sent to the school. Someone will contact you.` |

Parent identity is the phone number only (no PIN) in MVP. Known limitation: shared phones. Note in `docs/ASSUMPTIONS.md`.

### 7.3 Engine contract (implement exactly)

```python
def handle_ussd(session_id, service_code, phone, text) -> tuple[str, str]:  # ("CON"|"END", body)
    inputs = [] if text == "" else text.split("*")
    n = len(inputs)
    # 1. Idempotency: if ussd_requests has (session_id, n) return the cached response unchanged.
    # 2. Load identity (7.1). Build machine = Machine(ctx). state = machine.start()
    # 3. for inp in inputs: state = state.advance(inp)    # PURE: no I/O except read-only lookups
    #    - handles reserved keys (0 back, 00 cancel, 9 next) per screen flags
    #    - PIN node: if ussd_sessions.authed is True, consume without verifying
    # 4. If the LAST transition reached a commit node: run side effects in one transaction, return END.
    # 5. Render (kind, body); assert len(body) <= 182; store in ussd_requests; return.
    # 6. Any exception -> ("END", S_ERROR) and log with screen_key (never with text).
```

Because AT appends every input to `text`, the "back" key `0` is just another input; the reducer pops navigation state rather than the input list. Write property tests: replaying the same `text` always yields the same screen.

---

## 8. Rules engine

Runs (a) after new absences are committed and (b) nightly at 00:30 Africa/Kigali for open cases, SLA checks and auto-resolve.

**Metrics per student** (over submitted school days only; days with no class submission are skipped and counted as data gaps):
- `consecutive_days`: consecutive active absences on school days, ending at the latest submitted day.
- `absences_30d`: active absences in the last 30 calendar days.
- `absences_term`: active absences in the current term.

**Triggers**
1. **Level 1 (every absence):** parent SMS `parent_absence`, once per child per day (`dedupe_key = absence:{student_id}:{date}`). Respect `sms_opt_out` and quiet hours (defer to 07:00).
2. **Level 2, open case:** `consecutive_days >= RULE_CONSECUTIVE_DAYS` OR `absences_30d >= RULE_MONTHLY_ABSENCES`. Create case (`level=2`), assign mentor, SMS parent (`parent_case_opened`) and mentor (`mentor_new_case`), add `case_events`.
3. **Level 3, escalate to SEO:** any of: `absences_term >= RULE_ESCALATE_TERM_ABSENCES`; mentor outcome `needs_sector_help`; no visit within `RULE_VISIT_SLA_SCHOOL_DAYS + 2` school days of assignment. Set `sector_officer_id`, SMS SEO `seo_escalation`.
4. **Level 4, escalate to district:** case at level 3 unresolved for `RULE_DISTRICT_ESCALATION_DAYS` days.
5. **Auto-resolve:** student has `RULE_RETURN_STREAK_SCHOOL_DAYS` consecutive submitted school days with no absence → `resolved_returned`.
6. **Reopen:** a new trigger within 30 days of resolution reopens the same case (`reopened_count += 1`, event logged) instead of creating a new one.

**Mentor assignment:** among active mentors in the school's sector with fewer than `MENTOR_MAX_ACTIVE_CASES` active cases, pick the least loaded (tie: fewest total cases). None available → case stays `open`, unassigned, appears on the SEO dashboard.

**Risk score (0–100, for sorting and prioritisation only, not a prediction):**
`min(absences_30d,10)*5 + 15 if grade in (5,6) + 10 if is_repeater + 10 if over-age (birth_year implies age ≥ expected+2) + 10 if a prior case in last 12 months`. Weights live in `app_settings`, tunable after the pilot.

All thresholds are read from `app_settings` (fall back to env defaults). Every automatic action writes a `case_events` row.

---

## 9. SMS templates

Keys map to `sms_outbox.template_key`. EN below is the source of truth; **RW/FR strings are drafts to be verified by a native speaker** (owner: project lead). Keep ≤ 160 chars, no accents. `{code}` = `USSD_SERVICE_CODE_DISPLAY`.

| Key | To | EN |
|---|---|---|
| `parent_absence` | guardian | `Garuka: {child} was marked absent at {school} on {date}. Dial {code} to tell us why.` |
| `parent_case_opened` | guardian | `Garuka: {child} has missed several school days. A mentor may visit to help. Dial {code} for support.` |
| `parent_visit_code` | guardian | `Garuka visit code: {vcode}. Give it only to mentor {mentor} at your home. Valid 30 min.` |
| `mentor_new_case` | mentor | `Garuka: new case {ref}. {child}, {class}, {school}. Dial {code} > My cases.` |
| `mentor_visit_due` | mentor | `Garuka: visit for case {ref} is due by {date}. Dial {code} > My cases.` |
| `seo_escalation` | SEO | `Garuka: case {ref} escalated at {school}. Open the dashboard to review.` |
| `head_missing_submission` (optional) | head teacher | `Garuka: attendance not saved today for {n} class(es). Please remind teachers.` |

RW draft for the main message (verify): `parent_absence` → `Garuka: {child} ntiyaje ku ishuri ku wa {date}. Hamagara {code} utubwire impamvu.`

Rules: parent SMS never includes the reason, diagnosis, poverty status or other sensitive detail; use the child's first name only.

---

## 10. REST API (v1)

Base: `/api/v1`. JSON. Dates ISO 8601 (`2026-10-05`), timestamps UTC. IDs are UUIDs. Auth: `Authorization: Bearer <access_token>`.
Lists: `?page=1&page_size=20` → `{ "items": [...], "page": 1, "page_size": 20, "total": 134 }`.
Errors: `{ "error": { "code": "FORBIDDEN", "message": "...", "details": {} } }` with proper HTTP status.
Publish OpenAPI at `/openapi.json` and Swagger at `/docs`. Use explicit `response_model` and `operation_id` on every route (frontend generates types from it).

### 10.1 RBAC scope (enforce server-side on every query)

| Role | Scope | Can |
|---|---|---|
| admin | all | everything |
| district_director | own district | read all in district; notes; escalate/resolve level 4 |
| sector_officer | own sector | read schools/cases in sector; manage mentors; assign; resolve; confirm `moved_away`; manage help requests |
| head_teacher | own school | manage classes/students/teachers/guardians; mark attendance via dashboard; notes; view cases |
| teacher / mentor | (USSD only in MVP) | no dashboard login required |

### 10.2 Endpoints

| Method + path | Roles | Notes |
|---|---|---|
| `POST /auth/login` | public | `{email, password}` → `{access_token, refresh_token, token_type, user}` |
| `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` | any | |
| `GET /districts`, `GET /sectors?district_id=`, `GET /schools?sector_id=&q=` | scoped | |
| `POST/PATCH /schools`, `POST /sectors`, `POST /districts` | admin | |
| `GET/POST/PATCH /users` | admin; sector_officer (mentors); head_teacher (teachers) | `POST` sets `pin_hash=null`; user creates PIN on first USSD dial |
| `POST /users/{id}/reset-pin` | same as above | sets `pin_hash=null`, clears lock |
| `GET/POST /schools/{id}/classes`, `PATCH /classes/{id}` | admin, head_teacher | |
| `GET /students?school_id=&class_id=&q=&status=` | scoped | |
| `POST/PATCH /students`, `POST /students/{id}/guardians` | admin, head_teacher | |
| `POST /students/import` | admin, head_teacher | multipart CSV → `{created, updated, skipped, errors:[{row, message}]}`; dry-run with `?dry_run=true` |
| `GET /classes/{id}/attendance?date=` | scoped | |
| `POST /classes/{id}/attendance` | head_teacher, admin | `{date, absent_student_ids[]}` (dashboard fallback; same commit logic as USSD) |
| `DELETE /absences/{id}` | head_teacher, admin | voids an absence (audit logged) |
| `GET /attendance/compliance?school_id=&from=&to=` | scoped | class × day grid: `submitted|missing|non_school_day` |
| `GET /cases?status=&level=&school_id=&sector_id=&mentor_id=&q=&page=` | scoped | |
| `GET /cases/{id}` | scoped | full detail (see 10.3) |
| `PATCH /cases/{id}/assign` | sector_officer, admin | `{mentor_id}` |
| `POST /cases/{id}/escalate` | head_teacher, sector_officer | `{to_level, note}` |
| `POST /cases/{id}/notes` | head_teacher, sector_officer, district_director, admin | `{text}` |
| `POST /cases/{id}/resolve` | sector_officer, district_director, admin | `{outcome, note}`; outcomes `resolved_returned|closed_moved|closed_other` |
| `GET /mentors` | sector_officer, admin, district_director | `[ {id, name, phone, sector, active_cases, visits_30d, verified_rate} ]` |
| `GET /help-requests`, `PATCH /help-requests/{id}` | head_teacher, sector_officer, admin | `{status}` |
| `GET /analytics/overview` | scoped | KPIs (10.3) |
| `GET /analytics/trends?granularity=week&from=&to=` | scoped | absences and new cases series |
| `GET /analytics/reasons` | scoped | counts by reason and by barrier |
| `GET /analytics/schools/compare` | sector_officer, district_director, admin | per school: absence rate, open cases, compliance %, return rate |
| `GET /analytics/mentors` | sector_officer, admin | performance |
| `GET/PUT /settings/thresholds` | admin | |
| `GET /sms/outbox?status=` | admin | |
| `GET /audit-logs` | admin | |
| `GET /health` | public | `{status, db, version}` |
| `POST /ussd/{secret}` | AT | section 3 |
| `POST /webhooks/at/sms-delivery/{secret}` | AT | section 3.4 |
| `POST /dev/ussd` | dev only | section 3.6 |

All list endpoints accept `format=csv` where a table is shown on the dashboard (cases, students, absences, compliance).

### 10.3 Response examples (frontend builds against these)

`GET /analytics/overview`
```json
{
  "as_of": "2026-10-05T08:00:00Z",
  "scope": { "level": "sector", "name": "Tumba" },
  "kpis": {
    "students_active": 1840,
    "absent_today": 96,
    "open_cases": 41,
    "new_cases_7d": 12,
    "visits_overdue": 5,
    "returned_30d": 9,
    "attendance_compliance_pct": 87.5
  },
  "cases_by_level": { "2": 30, "3": 9, "4": 2 }
}
```

`GET /cases/{id}`
```json
{
  "id": "…", "ref": "GK-2026-000123", "status": "mentor_assigned", "level": 2,
  "risk_score": 62, "opened_at": "2026-10-01T07:12:00Z", "trigger": "consecutive",
  "student": { "id": "…", "name": "Uwase Jeanne", "class": "P5 A", "school": "GS Demo 1", "roll_number": 12 },
  "guardians": [ { "name": "…", "phone_masked": "+25078****001", "relationship": "mother" } ],
  "mentor": { "id": "…", "name": "…" },
  "absences": [ { "date": "2026-10-01", "reason_code": "COST", "reason_source": "parent" } ],
  "visits": [ { "started_at": "…", "verified": true, "outcome": "plan_agreed", "barrier_code": "COST" } ],
  "help_requests": [],
  "timeline": [ { "type": "opened", "at": "…", "actor": null, "payload": {} } ],
  "metrics": { "consecutive_days": 4, "absences_30d": 6, "absences_term": 8 }
}
```

Mask phone numbers in all dashboard responses except for admin. Do not return `pin_hash`, `password_hash` or any secret anywhere.

---

## 11. Frontend specification (agy)

**Users:** head teachers, sector officers, district directors, admins. Often on modest laptops and slow connections: keep bundles small, avoid heavy libraries, use skeleton loaders and pagination.

**Nav by role**
- head_teacher: Overview, Cases, Students, Classes & Attendance, Help requests.
- sector_officer: Overview, Cases, Schools compare, Mentors, Help requests.
- district_director: Overview, Schools compare, Cases (read-mostly), Reports.
- admin: all + Users, Schools, Settings, SMS outbox, Audit log.

**Pages and components**
1. **Login** — email + password, error states, redirect by role.
2. **Overview** — KPI cards (active cases, new 7d, overdue visits, compliance %, returned 30d); line chart of weekly absences; bar chart of absence reasons; cases-by-level funnel; "needs attention" list (overdue visits, unassigned cases, classes with missing attendance).
3. **Cases list** — table with filters (status, level, school, mentor, search), sortable by risk score, status pills, level badges, CSV export.
4. **Case detail** — student header, metrics, absence calendar (heatmap by day with reason colors), visits list with "verified / unverified" badge, timeline, notes box, actions (assign, escalate, resolve) shown per role permission.
5. **Students** — list/search, add/edit, guardian links, **CSV import wizard** (upload → dry-run preview with row errors → confirm). Provide a downloadable CSV template (`student_code,full_name,sex,birth_year,class_name,roll_number,guardian_name,guardian_phone,guardian_relationship`).
6. **Classes & attendance** — compliance grid (class × last 10 school days: submitted / missing / non-school day); manual attendance entry form (fallback when USSD fails).
7. **Mentors** — list with active cases, visits, verified rate; assign/unassign; add mentor (creates user).
8. **Schools compare** — sortable table + bar chart (absence rate, open cases, return rate, compliance).
9. **Help requests** — inbox with status change.
10. **Admin:** Users, Schools/Sectors/Districts, Settings (thresholds form with validation and defaults), SMS outbox (status filter, retry), Audit log (filters).
11. **Optional:** "USSD simulator" page using `POST /dev/ussd` (dev builds only).

**Requirements**
- Typed API client generated from `/openapi.json` (`openapi-typescript`). Until the backend is ready, use **MSW mocks** matching section 10.3.
- Token handling: keep access token in memory; refresh via refresh token; redirect on 401.
- i18n: `en` and `rw` via `next-intl`; all strings externalized (rw copy may start as English placeholders).
- Responsive (≥ 360 px), keyboard accessible, WCAG AA contrast, consistent empty/error/loading states.
- Never render `pin_hash` or unmasked phone numbers to non-admins.
- Env: `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000/api/v1`).
- Design: clean, calm, data-dense but readable; status colors used consistently (level 2 amber, level 3 orange, level 4 red, resolved green) and never as the only signal (add icons/text).

---

## 12. Seed data (`scripts/seed.py`, idempotent)

All phone numbers are fake and use `+2507800000NN`. Seed dummy PINs (`4821` etc.) **only in development**.

- 1 district (Huye), 1 sector (Tumba), 2 schools (`GS Demo 1`, `GS Demo 2`).
- Users: 1 admin, 1 district_director, 1 sector_officer, 1 head_teacher, 2 teachers (`+250780000001`, `+250780000002`), 2 mentors (`+250780000011`, `+250780000012`). Dashboard users have email + password `ChangeMe123!` (dev only).
- 2 classes (P5 A, P6 A), 30 students with roll numbers, guardians (`+250780000101…`), some with two children.
- 2026 terms: leave placeholder rows clearly marked and editable; do not present them as official dates.
- A few historical absences so dashboards have data, and 1 open case.

---

## 13. Delivery plan and task split

Backend = **B**, Frontend = **F**. **Both streams are built by agy.** Inside each milestone, finish and test the B tasks first, then do the F tasks against the real API (use the MSW mocks only for pages whose endpoints don't exist yet). Each milestone ends with a demo that works through AT sandbox where relevant.

Codex's only job in this plan is the up-front analysis and `docs/BLUEPRINT.md`. Optionally, if the project lead has spare Codex tokens later, Codex can do a **read-only review** of a finished milestone (checks against sections 3, 7, 8 and 15) and report findings, without editing code.

| # | Milestone | B tasks | F tasks | Done when |
|---|---|---|---|---|
| M0 | Foundations + hello-USSD | repo, compose, config, Alembic, `/health`, OpenAPI stubs (schemas only), **`/ussd/{secret}` returning `CON Hello Garuka`**, Makefile | Next.js scaffold, layout, auth pages, MSW mocks from 10.3, API client generation | Dialing the AT sandbox code shows "Hello Garuka" through ngrok; frontend runs on mocks |
| M1 | Core data + auth | models, migrations, JWT auth, RBAC, geography/users/classes/students/guardians, CSV import, seed, audit log | Login, role nav, Students + import wizard, Users/Schools admin | Import a CSV via dashboard; RBAC verified by tests |
| M2 | Teacher USSD + attendance + SMS | identity, PIN flow, teacher screens, submissions/absences, SMS outbox + console/AT providers, quiet hours, dedupe | Classes & attendance grid, manual entry | Teacher marks absences by USSD; parent SMS appears (console log and AT simulator) |
| M3 | Rules engine + cases + mentor | rules engine, scheduler, cases, mentor assignment, mentor USSD, visit codes, escalation | Cases list/detail, mentors page, actions | 3-day absence opens a case, mentor is notified, visit logged via USSD |
| M4 | Parent USSD + help | parent flows, reasons, help requests | Help inbox, reason charts | Parent explains an absence and asks for help |
| M5 | Analytics + polish | analytics endpoints, CSV export, settings endpoints | Overview, schools compare, settings, SMS outbox, audit UI | Dashboards populated from seed and live data |
| M6 | Hardening | rate limits, purge jobs, load test USSD, docs | a11y pass, error states, i18n rw strings | Test suite green, pilot checklist complete |

**Single-builder protocol (agy):** commit the M0 OpenAPI stubs first so the frontend has a stable contract. Generate frontend types from `/openapi.json`. Do not change a response shape without logging it per section 16. Work in small commits (one feature per commit) so progress survives if the token budget runs out mid-milestone, and keep a running `docs/PROGRESS.md` (done / in progress / next) so a new session can resume without re-reading everything.

---

## 14. Testing

### 14.1 Automated (must exist)

- **USSD engine unit tests:** first request per role; every screen ≤ 182 chars; back/cancel keys; invalid input; replay determinism; PIN setup, wrong PIN, lockout (3 fails), authed-session replay; unregistered phone; both-roles phone.
- **Idempotency test:** posting the identical `(sessionId, text)` twice produces one DB write and identical response.
- **Attendance:** commit creates absences + SMS outbox rows once; replace flow voids removed absences; zero-absence submission recorded.
- **Rules:** consecutive/monthly triggers, weekends and holidays skipped, data gaps skipped, level 2→3→4 escalation, SLA breach, auto-resolve, reopen.
- **Visit verification:** correct code, wrong code lockout, no-code (unverified) path.
- **RBAC:** each role can only see its scope; forbidden actions return 403.
- **Webhook:** wrong secret handled without leaking; exceptions always produce `END`.
- **Logging test:** ensure no PIN or raw `text` appears in logs.

### 14.2 Manual smoke test with curl (no AT needed)

```bash
SECRET=change-me-long-random
URL=http://localhost:8000/api/v1/ussd/$SECRET
# First request (empty text)
curl -s -X POST "$URL" \
  -d sessionId=ATUid_test1 -d serviceCode='*384*1234#' \
  -d phoneNumber=+250780000001 -d networkCode=99999 -d text=""
# Second request: PIN, then menu option 1
curl -s -X POST "$URL" \
  -d sessionId=ATUid_test1 -d serviceCode='*384*1234#' \
  -d phoneNumber=+250780000001 -d networkCode=99999 -d text="4821*1"
```

### 14.3 End-to-end through AT sandbox + ngrok

1. Follow section 3.5 and dial from the simulator with a seeded phone number.
2. Walk the teacher flow, then confirm rows in `absences` and `sms_outbox`.
3. Check the AT simulator SMS view (when `SMS_PROVIDER=africastalking`) or the API logs (console provider).
4. Use the ngrok inspector to confirm latency and that responses start with `CON`/`END`.

### 14.4 Acceptance criteria (MVP)

- A teacher marks 3 absent students in under 60 seconds, in ≤ 8 USSD steps after PIN.
- USSD p95 latency < 1 s locally; no request ever returns non-200.
- Parent SMS is queued within 1 minute of saving attendance and respects quiet hours.
- A case opens automatically on the configured triggers and appears on the dashboard within 1 minute.
- Every dashboard query is scope-filtered by role, with tests proving it.
- No PIN or raw `text` in any log or table.

---

## 15. Security, privacy and compliance notes

- Minors' data is sensitive. Keep student fields minimal (name, sex, birth year, class, roll number). No home addresses, no health details, no reasons in SMS.
- Record guardian **consent** (`consent_at`, `consent_source`) before sending SMS; respect `sms_opt_out`.
- RBAC + audit logs on reads of case details and all writes.
- Argon2 for passwords and PINs; short-lived JWTs; login rate limiting.
- Data retention: purge `ussd_requests` after 24 h; define retention for cases and SMS bodies (proposal: 24 months) in `docs/ASSUMPTIONS.md`.
- Rwanda's personal data protection law (Law N° 058/2021) applies: have a legal adviser review consent, retention, and data-sharing before any real pilot with real children's data. Do not use real student data in development.
- Secrets only in env vars; never commit `.env`.

---

## 16. Contract change protocol

1. Propose the change in `docs/API-CHANGELOG.md` (date, endpoint, before/after, reason).
2. Update the backend OpenAPI and tests, then regenerate the frontend types.
3. Breaking changes need the project lead's approval noted in the changelog before merging.

---

## 17. Assumptions to confirm (owner: project lead)

1. Threshold values in section 8 (3 days / 5 per month / 10 per term / 3-day visit SLA) suit the pilot schools.
2. Kinyarwanda copy for all USSD screens and SMS templates (drafts need native review).
3. AT Rwanda production requirements: dedicated USSD code lead time, sender ID registration, per-session and per-SMS pricing. Verify with AT before committing to a pilot date.
4. Whether MINEDUC/District will allow SDMS student ID import and later API access.
5. Who pays for SMS and mentors during the pilot (funder or partner) and how mentor stipends are recorded (not in MVP).
6. Parent authentication by phone number only is acceptable for the pilot.
7. Term dates and holidays for the pilot year.

---

## 18. Definition of done for the whole MVP

- All milestones M0–M6 complete, tests green in CI (`make test`).
- A recorded demo: teacher marks absences by USSD via AT sandbox + ngrok → parent SMS → case opens → mentor logs a verified visit by USSD → SEO sees the escalation on the dashboard.
- `docs/ASSUMPTIONS.md` and `docs/API-CHANGELOG.md` up to date; `README` explains setup in ≤ 10 commands.
