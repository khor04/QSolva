from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str
    gemini_api_key: str
    embedding_model: str = "gemini-embedding-001"
    llm_model: str = "gemini-flash-lite-latest"
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
