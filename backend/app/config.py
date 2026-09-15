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


settings = Settings()
