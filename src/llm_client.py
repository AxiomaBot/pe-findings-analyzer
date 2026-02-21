"""
Model-agnostic LLM client using LiteLLM.
Supports OpenAI, Anthropic, Azure, Ollama, and any OpenAI-compatible endpoint.
"""

import litellm
from src.config import LLMConfig

# Suppress LiteLLM verbose logging
litellm.suppress_debug_info = True


def chat(
    messages: list[dict],
    config: LLMConfig,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """
    Send a chat completion request.

    Args:
        messages: List of {"role": ..., "content": ...} dicts
        config: LLMConfig with model, api_key, api_base
        temperature: Lower = more deterministic (good for analysis)
        max_tokens: Max response length

    Returns:
        Response string
    """
    kwargs = {
        "model": config.model_string,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if config.api_key:
        kwargs["api_key"] = config.api_key

    if config.api_base:
        kwargs["api_base"] = config.api_base

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content


def check_connection(config: LLMConfig) -> tuple[bool, str]:
    """Quick connectivity check — sends a minimal request."""
    try:
        result = chat(
            messages=[{"role": "user", "content": "Reply with OK"}],
            config=config,
            max_tokens=10,
        )
        return True, result.strip()
    except Exception as e:
        return False, str(e)
