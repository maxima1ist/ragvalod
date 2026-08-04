"""RAG Orchestrator settings (prefix RAG_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50052
    qdrant_host: str = "qdrant"
    qdrant_grpc_port: int = 6334
    litellm_base_url: str = "http://litellm:4000"
    embedding_model_alias: str = "embedder-default"
    reranker_model_alias: str = "reranker-default"
    chat_model_alias: str = "chat-default"
    log_level: str = "INFO"
