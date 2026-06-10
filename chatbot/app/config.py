"""Application settings loaded from environment / .env file."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    @field_validator("openai_api_key")
    def validate_openai_api_key(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError(
                "OPENAI_API_KEY must be set in chatbot/.env or the environment. See chatbot/.env.example."
            )
        if value.strip() == "sk-replace-me":
            raise ValueError(
                "OPENAI_API_KEY is still the placeholder value. Replace it with a real OpenAI API key."
            )
        return value

    # Vector store
    chroma_persist_dir: str = "./data/chroma"
    website_collection: str = "website_content"
    projects_collection: str = "projects"

    # Retrieval
    retrieval_k: int = 4

    # CORS
    allowed_origins: str = (
        "http://localhost:3000,http://localhost:8081,http://127.0.0.1:8081,null"
    )

    @property
    def origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        for extra in [
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:8001",
            "http://127.0.0.1:8001",
            "null",
        ]:
            if extra not in origins:
                origins.append(extra)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
