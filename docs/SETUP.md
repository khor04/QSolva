# Local Setup

## 1. Supabase project

Create a project at supabase.com, then run the migration against it (see step 2).
Grab from Project Settings → API / Database:
- Project URL, anon key → frontend `.env`
- Project URL, connection string (use the pooler URL if not on a static IP), **service_role** secret → backend `.env`

The service_role key is separate from the anon key — never expose it to the frontend. It's only used server-side, to let a user delete their own account (self-service account deletion needs Supabase's Auth Admin API, which the anon key can't call).

Note: auth verification uses the project's JWKS endpoint (`SUPABASE_URL`), not a shared JWT secret — newer Supabase projects sign session tokens with ES256, not HS256.

## 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1      # PowerShell. Bash/git-bash: source .venv/Scripts/activate — macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env             # fill in DATABASE_URL, SUPABASE_URL, GEMINI_API_KEY
python -m alembic upgrade head   # applies the schema (tables, enums, RLS, auth trigger)
python -m uvicorn app.main:app --reload
```

Using `python -m <tool>` instead of the bare `pip`/`alembic`/`uvicorn` commands avoids relying on the `.venv\Scripts\*.exe` launcher stubs, which can end up broken on Windows (silent exit code 1, no error text — surfaces as "cannot find the specified file") independently of whether the underlying package installed fine.

If PowerShell refuses to run `Activate.ps1` with an execution-policy error, run once per session: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

Get a free `GEMINI_API_KEY` from Google AI Studio.

## 3. Storage bucket (for ticket attachments)

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

## 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # fill in VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
npm run dev
```

## Or via Docker Compose

Fill in both `.env` files first, then from the repo root:

```bash
docker compose up --build
```

This spins up both dev servers (backend hot-reloads via a `command:` override in `docker-compose.yml`; the images' own default `CMD`s are the production-safe versions used when deployed — see [DEPLOYMENT.md](DEPLOYMENT.md)).
