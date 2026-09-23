from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str
    # Server-side only — grants full admin access to Supabase Auth (e.g.
    # deleting a user outright). Never expose this to the frontend/browser;
    # it's unrelated to the anon key the frontend already uses. Optional so
    # existing setups don't break on upgrade — only self-account-deletion
    # needs it, and that endpoint checks for it explicitly.
    supabase_service_role_key: str | None = None
    gemini_api_key: str
    embedding_model: str = "gemini-embedding-001"
    llm_model: str = "gemini-flash-lite-latest"
    cors_origins: list[str] = ["http://localhost:5173"]
    # Business-hours clock for medium/low priority SLA targets (see
    # services/sla_policy.py) — critical/high run 24/7 regardless of these.
    # IANA zone name; defaults to UTC as a neutral placeholder. Set this to
    # the support team's actual timezone, or SLA due times will be wrong.
    business_timezone: str = "UTC"
    business_hours_start: int = 9
    business_hours_end: int = 18
    # Slack incoming webhook for admin-actionable alerts (critical/high
    # tickets, SLA risk, admin-directed escalations, new incidents) — see
    # services/alerts.py. Optional: alerts are skipped (in-app notifications
    # still work as normal) if this isn't set.
    admin_alert_slack_webhook_url: str | None = None
    # Used to build a clickable ticket link in those Slack alerts. Optional —
    # alerts are just plain text with no link if this isn't set.
    app_base_url: str | None = None


settings = Settings()
