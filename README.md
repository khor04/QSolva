# QSolva

AI-assisted internal IT service desk.

QSolva helps employees report and troubleshoot IT issues through a centralized
ticketing system. AI classifies ticket priority, while a RAG pipeline retrieves
relevant historical resolutions and generates a confidence-scored
"Try This First" recommendation.

Admins manage the ticket queue, resolve issues, monitor recurring problems,
and turn useful resolutions into reusable Help Center knowledge.

## Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** FastAPI, SQLAlchemy
- **Database:** PostgreSQL + pgvector
- **Platform:** Supabase
- **AI:** Google Gemini
- **Development:** Docker Compose

## Roles

### Staff

- Submit and track IT tickets
- Communicate with Admins
- Receive AI priority classification
- Get RAG-based troubleshooting recommendations
- Search the Help Center
- Confirm whether a suggested solution worked
- Receive ticket notifications

### Admin

- Manage the ticket queue
- Claim, unassign, and escalate tickets
- Communicate with Staff
- Review AI priority and resolution recommendations
- Retry failed AI analysis
- Monitor SLA-risk tickets
- Identify recurring IT issues
- Create and manage Help Center knowledge
- Monitor ticket and AI performance

Admin registration requires an invite code validated server-side.
Additional Admins can be invited directly from QSolva after the first Admin
has been created.

## Setup

Local dev setup (Supabase project, backend, frontend, or one-shot Docker Compose): see [docs/SETUP.md](docs/SETUP.md).

## Deployment

Frontend on Vercel, backend on Render (Docker), DB/auth/storage on Supabase — full steps and env vars in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Architecture

Design decisions and their rationale (AI-stage status tracking, retry concurrency handling, why the backend stays single-instance, etc.): see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## AI Workflow

```text
New Ticket
    ↓
AI Priority Classification
    ↓
Generate Embedding
    ↓
Semantic Search with pgvector
    ↓
Retrieve Similar Resolved Tickets
    ↓
Resolution Evidence
    ↓
Gemini
    ↓
"Try This First" Recommendation
    ↓
Staff Feedback




