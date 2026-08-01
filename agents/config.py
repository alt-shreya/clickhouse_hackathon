"""
Configuration utilities for Atlys agents.
Loads .env files and provides typed access to settings.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ClickHouseConfig:
    """ClickHouse connection configuration."""
    host: str
    port: int = 8443
    user: str = "default"
    password: str = ""
    database: str = "atlys"
    secure: bool = True
    
    @classmethod
    def from_env(cls) -> "ClickHouseConfig":
        """Load config from environment variables."""
        return cls(
            host=os.getenv("CLICKHOUSE_HOST", ""),
            port=int(os.getenv("CLICKHOUSE_PORT", "8443")),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("CLICKHOUSE_DATABASE", "atlys"),
            secure=os.getenv("CLICKHOUSE_SECURE", "true").lower() == "true",
        )
    
    def validate(self) -> list[str]:
        """Validate required fields."""
        errors = []
        if not self.host:
            errors.append("CLICKHOUSE_HOST is required")
        if not self.password:
            errors.append("CLICKHOUSE_PASSWORD is required")
        return errors


@dataclass
class LangfuseConfig:
    """Langfuse tracing configuration."""
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"
    enabled: bool = True
    
    @classmethod
    def from_env(cls) -> "LangfuseConfig":
        """Load config from environment variables."""
        host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
        return cls(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            host=host,
            enabled=bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")),
        )


@dataclass
class OpenRouterConfig:
    """OpenRouter LLM configuration."""
    api_key: str = ""
    model: str = "google/gemma-4-31b-it:free"
    base_url: str = "https://openrouter.ai/api/v1"
    enabled: bool = True
    
    @classmethod
    def from_env(cls) -> "OpenRouterConfig":
        """Load config from environment variables."""
        api_key = os.getenv("OPENROUTER_API_KEY", " ")
        return cls(
            api_key=api_key,
            model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            enabled=bool(api_key),
        )
    
    def get_client(self):
        """Get an OpenAI-compatible client for OpenRouter."""
        if not self.enabled:
            raise ValueError("OpenRouter not configured (missing API key)")
        try:
            from openai import OpenAI
            return OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,
                max_retries=1,
            )
        except ImportError:
            raise ImportError("openai package required: pip install openai")


def load_dotenv(env_path: Optional[Path] = None) -> bool:
    """
    Load environment variables from .env file.
    Returns True if loaded, False if file not found.
    """
    if env_path is None:
        # Search from cwd and from this package so running from repo root still works.
        search_roots = [Path.cwd(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent]
        seen = set()
        for root in search_roots:
            for parent in [root] + list(root.parents):
                if parent in seen:
                    continue
                seen.add(parent)
                env_file = parent / ".env"
                if env_file.exists():
                    env_path = env_file
                    break
            if env_path is not None:
                break
    
    if env_path is None or not env_path.exists():
        return False
    
    try:
        # Try python-dotenv first
        from dotenv import load_dotenv as _load_dotenv
        _load_dotenv(env_path, override=False)
        return True
    except ImportError:
        # Fallback: simple parser
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
        return True


def get_config() -> tuple[ClickHouseConfig, LangfuseConfig, OpenRouterConfig]:
    """Load all configs from environment."""
    # Try to load .env
    load_dotenv()
    
    ch_config = ClickHouseConfig.from_env()
    lf_config = LangfuseConfig.from_env()
    or_config = OpenRouterConfig.from_env()
    
    return ch_config, lf_config, or_config
