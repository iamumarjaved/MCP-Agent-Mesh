"""Centralized configuration management using Pydantic settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureOpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_")

    endpoint: str = ""
    api_key: str = ""
    api_version: str = "2024-12-01-preview"
    deployment_gpt4o: str = "gpt-4o"
    deployment_gpt4o_mini: str = "gpt-4o-mini"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    ssl: bool = False
    context_ttl_seconds: int = 7200  # 2 hours
    registry_ttl_seconds: int = 120


class CosmosDBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COSMOS_")

    endpoint: str = ""
    key: str = ""
    database_name: str = "agentmesh"
    task_container: str = "tasks"
    audit_container: str = "audit_log"


class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    host: str = "localhost"
    port: int = 6333
    collection_name: str = "knowledge_base"
    embedding_dim: int = 1536


class BlobStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BLOB_")

    connection_string: str = ""
    container_data: str = "data"
    container_reports: str = "reports"


class LangfuseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANGFUSE_")

    public_key: str = ""
    secret_key: str = ""
    host: str = "http://localhost:3000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "MCP Agent Mesh"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", alias="ENV")
    debug: bool = False
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    cors_origins: list[str] = ["*"]

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Agent defaults
    agent_default_timeout_seconds: float = 60.0
    agent_max_retries: int = 3
    agent_heartbeat_interval_seconds: int = 30

    # Budget
    task_budget_limit_usd: float = 1.00
    budget_warning_threshold: float = 0.80  # 80% triggers warning

    # Guardian thresholds
    guardian_auto_approve_threshold: float = 0.85
    guardian_warning_threshold: float = 0.60
    guardian_reprocess_threshold: float = 0.40

    # HITL
    hitl_timeout_minutes: int = 30

    # MCP cache
    mcp_cache_ttl_seconds: int = 300  # 5 minutes

    # Sub-settings
    azure_openai: AzureOpenAISettings = AzureOpenAISettings()
    redis: RedisSettings = RedisSettings()
    cosmos: CosmosDBSettings = CosmosDBSettings()
    qdrant: QdrantSettings = QdrantSettings()
    blob: BlobStorageSettings = BlobStorageSettings()
    langfuse: LangfuseSettings = LangfuseSettings()

    # Dashboard
    dashboard_port: int = 8501
    websocket_url: str = "ws://localhost:8000/ws"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
