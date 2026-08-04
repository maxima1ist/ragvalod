"""Ingestion Service settings (prefix INGESTION_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGESTION_", env_file=".env", extra="ignore")

    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051
    qdrant_host: str = "qdrant"
    qdrant_grpc_port: int = 6334
    qdrant_http_port: int = 6333
    litellm_base_url: str = "http://litellm:4000"
    litellm_api_key: str = "sk-ragvalod-local"
    embedding_model_alias: str = "embedder-default"
    # Fixed into collection manifest at creation time (must match Infinity/LiteLLM backend).
    embedding_model_name: str = "intfloat/multilingual-e5-small"
    embedding_doc_prefix: str = "passage: "
    embedding_batch_size: int = 64
    embedding_vector_size: int = 384
    chunk_size: int = 512
    chunk_overlap: int = 100
    collection_name: str = "documents"
    local_files_dir: str = "/data/local_files"
    log_level: str = "INFO"
