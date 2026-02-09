"""Tests for src.core.config -- configuration loading and validation."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestSettings:
    """Test the Settings class and its sub-settings."""

    def test_default_settings_load(self) -> None:
        """Settings can be instantiated with default values."""
        from src.core.config import Settings

        s = Settings()
        assert s.app_name == "MCP Agent Mesh"
        assert s.app_version == "1.0.0"
        assert s.api_port == 8000
        assert s.debug is False

    def test_environment_default(self) -> None:
        """Default environment is 'development'."""
        from src.core.config import Settings

        s = Settings()
        # The ENV alias is used, but in test the env var may be set to 'test'
        assert s.environment in ("development", "test")

    def test_redis_settings_defaults(self) -> None:
        """RedisSettings has sensible defaults."""
        from src.core.config import RedisSettings

        r = RedisSettings()
        assert r.host == "localhost"
        assert r.port == 6379
        assert r.db == 0
        assert r.context_ttl_seconds == 7200

    def test_qdrant_settings_defaults(self) -> None:
        """QdrantSettings has sensible defaults."""
        from src.core.config import QdrantSettings

        q = QdrantSettings()
        assert q.host == "localhost"
        assert q.port == 6333
        assert q.collection_name == "knowledge_base"
        assert q.embedding_dim == 1536

    def test_langfuse_settings_defaults(self) -> None:
        """LangfuseSettings has sensible defaults."""
        from src.core.config import LangfuseSettings

        lf = LangfuseSettings()
        assert lf.host == "http://localhost:3000"
        assert lf.public_key == ""

    def test_azure_openai_settings_defaults(self) -> None:
        """AzureOpenAISettings has sensible defaults."""
        from src.core.config import AzureOpenAISettings

        ai = AzureOpenAISettings()
        assert ai.api_version == "2024-12-01-preview"
        assert ai.deployment_gpt4o == "gpt-4o"

    def test_budget_thresholds(self) -> None:
        """Budget thresholds are in expected ranges."""
        from src.core.config import Settings

        s = Settings()
        assert 0 < s.task_budget_limit_usd <= 10.0
        assert 0 < s.budget_warning_threshold < 1.0

    def test_guardian_thresholds_ordering(self) -> None:
        """Guardian thresholds are ordered correctly: auto > warning > reprocess."""
        from src.core.config import Settings

        s = Settings()
        assert s.guardian_auto_approve_threshold > s.guardian_warning_threshold
        assert s.guardian_warning_threshold > s.guardian_reprocess_threshold

    def test_settings_env_override(self) -> None:
        """Environment variables override default settings."""
        from src.core.config import Settings

        with patch.dict(os.environ, {"API_PORT": "9999", "DEBUG": "true"}):
            s = Settings()
            assert s.api_port == 9999
            assert s.debug is True

    def test_get_settings_returns_same_instance(self) -> None:
        """get_settings() is cached and returns the same instance."""
        from src.core.config import get_settings

        # Clear any existing cache
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        get_settings.cache_clear()

    def test_sub_settings_are_populated(self) -> None:
        """Settings includes all sub-settings objects."""
        from src.core.config import Settings

        s = Settings()
        assert s.azure_openai is not None
        assert s.redis is not None
        assert s.cosmos is not None
        assert s.qdrant is not None
        assert s.blob is not None
        assert s.langfuse is not None

    def test_cors_origins_default(self) -> None:
        """Default CORS origins allow all."""
        from src.core.config import Settings

        s = Settings()
        assert "*" in s.cors_origins
