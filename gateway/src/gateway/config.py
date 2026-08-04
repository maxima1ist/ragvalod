"""Gateway settings loaded from environment (prefix GATEWAY_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GATEWAY_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str = ""
    ingestion_grpc_addr: str = "ingestion:50051"
    rag_grpc_addr: str = "rag_orchestrator:50052"
    litellm_base_url: str = "http://litellm:4000"
    log_level: str = "INFO"
