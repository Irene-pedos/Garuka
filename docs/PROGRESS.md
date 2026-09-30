# Project Progress Tracker

## Milestone M0: Foundations + Hello-USSD

- [x] M0.1: Initialize mono-repo structure, `.env.example`, gitignore, and Makefile.
- [x] M0.2: Database connectivity and configuration (PostgreSQL 16 & docker-compose.yml).
- [x] M0.3: FastAPI core setup with settings, logging (no-PIN/raw text rule), and `/health` route.
- [x] M0.4: `/api/v1/ussd/{secret}` webhook returning `CON Hello Garuka`.
- [x] M0.5: USSD response validation (<= 182 chars) and global exception handling.
- [ ] M0.6: Next.js frontend scaffold in `apps/web` with shadcn preset (`b69EkWqpAe`).
- [ ] M0.7: OpenAPI typed client generation via `openapi-typescript`.

### Current State
- **Done:** M0.1 through M0.5 (FastAPI backend, health check, USSD Hello Garuka webhook, tests).
- **In Progress:** M0.6 - Scaffold Next.js dashboard in `apps/web` with shadcn preset.
- **Next:** M0.7 - OpenAPI client generation and ngrok + AT sandbox verification.
