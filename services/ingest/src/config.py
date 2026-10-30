from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application runtime configuration validated with Pydantic.
    Reads environment variables and .env file automatically.
    """
    APP_NAME: str = "Platina AI — Ingestion & RAG Service"
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    LOG_LEVEL: str = "info"

    # Database & Vector Store (Configured in upcoming milestones)
    DATABASE_URL: str = "postgresql://platina:platina123@localhost:5432/platina_rag"

    # Embedding model configuration
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384

    # Pipeline v2: On-demand live scraping flag (default false)
    ON_DEMAND_INGESTION: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
