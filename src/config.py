"""
Configuration management for the LLM backend.
Reads from .env file or Streamlit session state (sidebar overrides).
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: Optional[str]
    api_base: Optional[str]

    @property
    def model_string(self) -> str:
        """LiteLLM model string format: provider/model"""
        return f"{self.provider}/{self.model}"


def load_config_from_env() -> LLMConfig:
    """Load LLM config from environment variables."""
    return LLMConfig(
        provider=os.getenv("LLM_PROVIDER", "openai"),
        model=os.getenv("LLM_MODEL", "gpt-4o"),
        api_key=os.getenv("LLM_API_KEY") or None,
        api_base=os.getenv("LLM_API_BASE") or None,
    )


def config_from_ui(provider: str, model: str, api_key: str, api_base: str) -> LLMConfig:
    """Build config from sidebar UI inputs."""
    return LLMConfig(
        provider=provider.strip(),
        model=model.strip(),
        api_key=api_key.strip() or None,
        api_base=api_base.strip() or None,
    )
