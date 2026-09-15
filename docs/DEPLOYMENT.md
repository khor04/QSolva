# Deployment

QSolva uses managed services where possible, with the frontend and backend deployed separately.

## Frontend

**Vercel**

- Root directory: `frontend`
- Framework: Vite
- Environment variables:
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_ANON_KEY`
  - `VITE_API_BASE_URL`
- `frontend/vercel.json` provides the SPA rewrite required by React Router.

## Backend

**Render**

- Docker deployment using `backend/Dockerfile`
- Health check: `/health`
- Environment variables:
  - `DATABASE_URL`
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY` (server-side only — never in the frontend's env vars)
  - `GEMINI_API_KEY`
  - `EMBEDDING_MODEL`
  - `LLM_MODEL`
  - `CORS_ORIGINS`

## Database

Run migrations against the production Supabase database:

```bash
python -m alembic upgrade head