# Project Progress Tracker

## Milestone M0: Foundations + Hello-USSD

- [x] M0.1: Initialize mono-repo structure, `.env.example`, gitignore, and Makefile.
- [x] M0.2: Database connectivity and configuration (PostgreSQL 16 on port 5433).
- [x] M0.3: FastAPI core setup with settings, logging (no-PIN/raw text rule), and `/health` route.
- [x] M0.4: `/api/v1/ussd/{secret}` webhook returning `CON Hello Garuka`.
- [x] M0.5: USSD response validation (<= 182 chars) and global exception handling.
- [x] M0.6: Next.js frontend scaffold in `apps/web` with shadcn preset (`b69EkWqpAe`).
- [x] M0.7: OpenAPI typed client generation via `openapi-typescript`.

### Active Environment (M0 Review)
- **Local API:** `http://localhost:8000`
- **ngrok Public URL:** `https://kizzy-sclerotized-verna.ngrok-free.dev`
- **AT USSD Callback URL:** `https://kizzy-sclerotized-verna.ngrok-free.dev/api/v1/ussd/change-me-long-random`
- **Frontend App:** `apps/web` (Next.js 16 + shadcn preset `b69EkWqpAe`)
- **Ngrok Web Inspector:** `http://127.0.0.1:4040`

### Current State
- **Done:** Milestone M0 complete. All automated unit tests passing (`9/9 passed`). Frontend builds with Turbopack. Public tunnel is active and accepting requests.
- **In Progress:** Pausing for user milestone review on Africa's Talking simulator as required.
- **Next:** Proceeding to Milestone M1 (Core Data, Database Models, JWT Auth, RBAC & CSV Import).
