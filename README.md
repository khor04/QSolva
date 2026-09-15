# QSolva
AI-assisted IT service desk. Staff submit tickets; a RAG pipeline over previously resolved tickets classifies priority and suggests a confidence-scored resolution; admins (who double as IT support) triage, reply, and resolve.

## Stack
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL + pgvector
- **Auth/DB/Storage**: Supabase
- **AI**: Google Gemini 
- **Dev**: Docker Compose

## Roles
Two roles only: `staff` (submits/tracks tickets) and `admin` (IT support — claims tickets from the queue, replies, resolves, sees the dashboard).
Registration always creates a `staff` account; promote to admin manually:

```sql
update public.users set role = 'admin' where email = 'someone@example.com';
```

## Setup

### 1. Supabase project
Create a project at supabase.com, then run the migration against it (see below).
Grab from Project Settings → API / Database:
- Project URL, anon key → frontend `.env`
- Project URL, connection string (use the pooler URL if not on a static IP) → backend `.env`

Note: auth verification uses the project's JWKS endpoint (`SUPABASE_URL`), not a shared JWT secret — newer Supabase projects sign session tokens with ES256, not HS256.

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1      # PowerShell. Bash/git-bash: source .venv/Scripts/activate — macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env             # fill in DATABASE_URL, SUPABASE_URL, GEMINI_API_KEY
python -m alembic upgrade head   # applies the schema (tables, enums, RLS, auth trigger)
python -m uvicorn app.main:app --reload
```

Using `python -m <tool>` instead of the bare `pip`/`alembic`/`uvicorn` commands avoids relying on the `.venv\Scripts\*.exe` launcher stubs, which can end up broken on Windows (silent exit code 1, no error text — surfaces to the user as "cannot find the specified file") independently of whether the underlying package installed fine.

If PowerShell refuses to run `Activate.ps1` with an execution-policy error, run once per session: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

Get a free `GEMINI_API_KEY` from Google AI Studio.

### 3. Storage bucket (for ticket attachments)
In the Supabase dashboard: Storage → New bucket → name it exactly `ticket-attachments` → Public.
Then in the SQL Editor:

```sql
create policy "Authenticated users can upload ticket attachments"
on storage.objects for insert
to authenticated
with check (bucket_id = 'ticket-attachments');

create policy "Public can view ticket attachments"
on storage.objects for select
to public
using (bucket_id = 'ticket-attachments');
```

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # fill in VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
npm run dev
```

### Or via Docker Compose

Fill in both `.env` files first, then from the repo root:

```bash
docker compose up --build
```

**Deployment**
Frontend: Vercel
Backend: Render with Docker
Database/Auth/Storage: Supabase
AI: Google Gemini
Configuration: Environment variables and production CORS
Database: Alembic migrations
## Modules

**Staff**

1. **Authentication & Account** — Supabase Auth with Staff/Admin roles, login, registration, and password reset.

2. **Ticket Management** — Submit tickets, view ticket history, communicate with Admin, and track ticket status.

3. **AI Assistance** — View AI-prioritized tickets and receive RAG-based "Try This First" troubleshooting suggestions with supporting evidence.

4. **Help Center** — Search admin-published troubleshooting articles to resolve common IT issues before submitting a ticket.

**Admin**

5. **Ticket Management** — Manage the ticket queue, search and filter tickets, claim or unassign tickets, and handle ticket resolution.

6. **AI Assistance** — Review AI-generated priority classifications and RAG-based resolution recommendations, with the ability to override or act on suggestions.

7. **Recurring Issues** — Automatically identify similar IT problems and provide insights into recurring issues, common symptoms, trends, and resolutions.

8. **Knowledge Management** — Generate AI-assisted Help Center articles from recurring issues and historical resolutions, then review, edit, publish, or unpublish them.

9. **Dashboard & Monitoring** — Monitor ticket activity, overdue tickets, AI performance, priority distribution, and emerging issues.

**Shared**

10. **Notifications** — Receive real-time in-app updates for ticket activity, replies, critical tickets, escalations, and resolution confirmation.

11. **Resolution Feedback** — Record resolution outcomes to evaluate AI performance and improve the reliability of historical resolution knowledge.

12. **SLA Monitoring** — Automatically identify tickets that exceed the defined resolution timeframe and notify the responsible Admin.


