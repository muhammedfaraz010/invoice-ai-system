import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # OpenAI (for embeddings and optional modules)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "invoice-embeddings"

    # Database
    database_url: str = "postgresql://invoice_user:invoice_pass@localhost:5432/invoice_db"

    # Security
    secret_key: str = "changeme_in_production"
    access_token_expire_minutes: int = 60

    # Storage
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 20

    # App
    app_env: str = "development"
    debug: bool = True
    cors_origins: str = "http://localhost:3000"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
os.makedirs(settings.upload_dir, exist_ok=True)
