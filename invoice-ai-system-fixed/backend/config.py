import os
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # OpenAI (optional)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Pinecone (optional)
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "invoice-embeddings"

    # Database — defaults to SQLite so project works without PostgreSQL setup
    database_url: str = "sqlite:///./invoice_ai.db"

    # Security
    secret_key: str = "changeme_in_production_use_a_long_random_string"
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

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str) and value.lower() == "release":
            return False
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
os.makedirs(settings.upload_dir, exist_ok=True)
