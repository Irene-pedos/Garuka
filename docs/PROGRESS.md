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
- [ ] M1.3: Implement password hashing (Argon2), JWT token generation, and `POST /auth/login`, `/me`.
- [ ] M1.4: Implement RBAC dependency system enforcing geographic/school scoping per role.
- [ ] M1.5: Build CRUD endpoints for schools, sectors, classes, and users with PIN reset.
- [ ] M1.6: Implement `POST /students/import` CSV handler with dry-run validation.
- [ ] M1.7: Write idempotent seed script (`scripts/seed.py`) with sample district, school, users.
- [ ] M1.8: Build web dashboard login, role-based navigation sidebar, and Users/Schools management.
- [ ] M1.9: Build Students list and CSV Import wizard with preview on dashboard.

### Current State
- **Done:** M1.1 & M1.2 complete. Complete schema of 24 tables with indexes and constraints migrated in PostgreSQL.
- **In Progress:** M1.3 - Security, password hashing (Argon2), JWT token issuance, and `/auth/login`, `/auth/refresh`, `/auth/me` endpoints.
- **Next:** M1.4 - RBAC scope dependencies and tests.
