"""
LLM Client Factory for MAHIKS-TR
=================================

Single entry point to create any LLM client.
Provider SDKs are imported lazily — an unused provider never blocks startup.

Usage:
    from backend.llm.factory import create_llm_client

    # For generation (picks up LLM_PROVIDER env var)
    client = create_llm_client()

    # For KG extraction (explicit provider + model override)
    client = create_llm_client("gemini", model="gemini-2.5-flash")

    # Then use it:
    response = client.chat(messages=[...])
    json_str = client.chat_json(messages=[...])
    for token in client.chat_stream(messages=[...]):
        print(token, end="")
"""
import os
from typing import Optional

from backend.agents.client.BaseLLMClient import BaseLLMClient
from backend.config import Config

class LLMClientFactory:

    @staticmethod
    def create_llm_client(
        provider: Optional[str] = None,
        usage: Optional[str] = None,
        **kwargs,
    ) -> BaseLLMClient:
        """
        Create an LLM client for the specified provider.

        Args:
            provider: "ollama", "openai", "openrouter", "gemini", "vertex".
                      Defaults to LLM_PROVIDER env var, then "ollama".
            model: Model override. Each provider has its own default via env vars.
            **kwargs: Extra args forwarded to the provider constructor
                      (e.g., api_key, base_url, project, location).

        Returns:
            BaseLLMClient instance
        """
        provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
        models = {}

        
        if usage == "kg_extraction":
            # For KG extraction, we might want to use a different provider/model than for generation.
            # In that case, we look for provider-specific env vars like KG_EXTRACTION_MODEL_OPENAI, etc.
            models["ollama"] = os.getenv("KG_OLLAMA_MODEL", Config.KG_OLLAMA_MODEL)
            models["openai"] = os.getenv("OPENAI_MODEL", Config.OPENAI_MODEL)
            models["openrouter"] = os.getenv("KG_OPENROUTER_MODEL", Config.KG_OPENROUTER_MODEL)
            models["gemini"] = os.getenv("KG_GEMINI_MODEL", Config.KG_GEMINI_MODEL)
            models["vertex"] = os.getenv("KG_VERTEX_MODEL", Config.KG_VERTEX_MODEL)

        elif usage == "evaluation":
            models["ollama"] = os.getenv("JUDGE_MODEL_OLLAMA", Config.JUDGE_MODEL_OLLAMA)
            models["gemini"] = os.getenv("JUDGE_MODEL_GEMINI", Config.JUDGE_MODEL_GEMINI)
            models["vertex"] = os.getenv("JUDGE_MODEL_VERTEX", Config.JUDGE_MODEL_VERTEX)
            models["openrouter"] = os.getenv("JUDGE_MODEL_OPENROUTER", Config.JUDGE_MODEL_OPENROUTER)
            models["openai"] = os.getenv("OPENAI_MODEL", Config.OPENAI_MODEL)

        elif usage == "generation":
            models["ollama"] = os.getenv("OLLAMA_MODEL", Config.OLLAMA_MODEL)
            models["openai"] = os.getenv("OPENAI_MODEL", Config.OPENAI_MODEL)
            models["openrouter"] = os.getenv("OPENROUTER_LLM_MODEL", Config.OPENROUTER_LLM_MODEL)
            models["gemini"] = os.getenv("GEMINI_MODEL", Config.GEMINI_MODEL)
            models["vertex"] = os.getenv("VERTEX_MODEL", Config.VERTEX_MODEL)

        
        if provider in ("ollama", "local"):
            from backend.agents.client.adapters.OllamaClient import OllamaClient
            return OllamaClient(model=models["ollama"], **kwargs)

        if provider == "openai":
            from backend.agents.client.adapters.OpenAIClient import OpenAIClient
            return OpenAIClient(model=models["openai"], **kwargs)

        if provider == "openrouter":
            from backend.agents.client.adapters.OpenAIClient import OpenAIClient
            return OpenAIClient.openrouter(model=models["openrouter"], **kwargs)

        if provider == "gemini":
            from backend.agents.client.adapters.GeminiClient import GeminiClient
            return GeminiClient(model=models["gemini"], **kwargs)

        if provider == "vertex":
            from backend.agents.client.adapters.VertexClient import VertexClient
            return VertexClient(model=models["vertex"], **kwargs)

        raise ValueError(
            f"Unknown LLM provider: {provider!r}. "
            f"Choose from: ollama, openai, openrouter, gemini, vertex"
        )