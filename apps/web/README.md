# Garuka — Web Operations Dashboard

Garuka (*"Come back to school"* in Kinyarwanda) is a primary school dropout early warning and rapid-intervention system built for Rwandan basic education. The web dashboard provides real-time, role-scoped operational workspaces for school leaders, sector education officers, district officials, and system administrators.

---

## Key Features & Workspaces

The dashboard is structured around operational action and strict Role-Based Access Control (RBAC):

| Role | Workspace & Capabilities |
|---|---|
| **Head Teacher** | • Submit and edit daily class attendance.<br>• School attendance compliance grid & CSV export.<br>• Monitor student absence patterns and open Level 2 cases.<br>• Request mentor home visits. |
| **Sector Education Officer (SEO)** | • Level 3 escalated cases queue and action center.<br>• Assign community mentors to at-risk student cases.<br>• Monitor mentor workload, visit SLA compliance, and OTP home-visit verification.<br>• Triage community & parent help requests. |
| **District Director (DDE)** | • Cross-sector and cross-school comparison dashboard (`/dashboard/schools-compare`).<br>• Attendance compliance metrics and chronic absenteeism trends.<br>• Unresolved case escalation tracking and SLA breach visibility. |
| **System Administrator** | • User management and role provisioning (`/dashboard/users`).<br>• School & class hierarchy configuration (`/dashboard/schools`).<br>• Dropout rule thresholds and holiday/term calendar configuration (`/dashboard/settings`).<br>• Outbox SMS delivery status monitor (`/dashboard/sms-outbox`).<br>• Tamper-evident system audit trail (`/dashboard/audit`). |

---

## Tech Stack

- **Framework**: [Next.js 16 (App Router)](https://nextjs.org/)
- **UI Runtime**: [React 19](https://react.dev/)
- **Language**: TypeScript 5 (Strict Mode)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Icons**: [Lucide React](https://lucide.dev/)
- **Type-safe API**: Auto-generated TypeScript types via `openapi-typescript` mapped to the FastAPI backend.

---

## Directory Structure

```
apps/web/
├── app/
│   ├── dashboard/
│   │   ├── page.tsx               # Role-scoped operational overview & action queue
│   │   ├── attendance/            # Daily attendance entry & compliance grid
│   │   ├── cases/                 # Case list with filters (status, level, school)
│   │   ├── cases/[id]/            # Case detail, timeline events, mentor visits
│   │   ├── help-requests/         # Community/parent help requests triage
│   │   ├── schools-compare/       # District & sector school comparison analytics
│   │   ├── schools/               # Schools directory
│   │   ├── students/              # Student roster and historical attendance
│   │   ├── mentors/               # Community mentors directory and caseloads
│   │   ├── users/                 # User provisioning and RBAC roles
│   │   ├── sms-outbox/            # Outgoing SMS monitor and delivery logs
│   │   ├── audit/                 # System audit log trail
│   │   └── settings/              # Dropout rules, term dates, and system settings
│   ├── login/                     # Secure authentication screen
│   ├── layout.tsx                 # Root layout with ThemeProvider
│   └── globals.css                # Global Tailwind CSS definitions
├── components/
│   ├── sidebar.tsx                # Dynamic, role-aware navigation sidebar
│   ├── header.tsx                 # Top navigation with user badge and logout
│   └── ui/                        # Reusable accessible UI primitives
└── lib/
    ├── api/
    │   ├── client.ts              # Centralized fetch client with token management
    │   └── schema.ts              # Generated OpenAPI types from backend
    └── auth.ts                    # Auth token storage and role helpers
```

---

## Getting Started

### 1. Prerequisites

- **Node.js**: `v20.x` or later
- **npm**: `v10.x` or later
- **Backend API**: The FastAPI service in `apps/api` should be running (default `http://localhost:8000`).

### 2. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env.local
```

Configure your environment variables:

```ini
# Backend API Base URL (including /api/v1 prefix)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

### 3. Installation & Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Build & Production

```bash
# Typecheck TypeScript files
npm run typecheck

# Build optimized production bundle
npm run build

# Start production server
npm run start
```

### 5. API Type Generation

When backend endpoints or schemas change in `apps/api`, regenerate TypeScript types:

```bash
npm run codegen
```

---

## Operating Conventions

- **Timezone**: All business dates and attendance calculations use **Africa/Kigali (UTC+2)**. The dashboard clearly labels Rwanda local time on operational reports.
- **Privacy & Minors' Data**:
  - Never display raw PINs or unmasked sensitive data.
  - Queries are strictly scoped by the authenticated user's role and administrative unit (School, Sector, or District).
  - Outbox SMS messages contain no medical or personal diagnoses.
