"""RAG Orchestrator settings (prefix RAG_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50052
    qdrant_host: str = "qdrant"
    qdrant_http_port: int = 6333
    qdrant_grpc_port: int = 6334
    collection_name: str = "documents"
    litellm_base_url: str = "http://litellm:4000"
    litellm_api_key: str = "sk-ragvalod-local"
    embedding_model_alias: str = "embedder-default"
    embedding_model_name: str = "intfloat/multilingual-e5-small"
    embedding_query_prefix: str = "query: "
    embedding_vector_size: int = 384
    reranker_model_alias: str = "reranker-default"
    chat_model_alias: str = "chat-default"
    default_top_k: int = 50
    default_rerank_top_n: int = 5
    default_temperature: float = 0.2
    default_max_tokens: int = 512
    log_level: str = "INFO"
