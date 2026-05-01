"""
OpenRouter KG extractor.

OpenRouter exposes hundreds of models via an OpenAI-compatible chat-completions
API, so we use the `openai` SDK with a custom `base_url`. The `openai` package
is already a project dep (used by generation_agent.py).

Required env: OPENROUTER_API_KEY, KG_OPENROUTER_MODEL (no default; fail fast).
Optional env: OPENROUTER_REFERER, OPENROUTER_TITLE (sent as ranking headers per
OpenRouter's docs).
"""
import os
from typing import Optional

from openai import OpenAI

from backend.agents.kg.KGExtractorTypeEnum import KGExtractorTypeEnum
from backend.agents.kg.KGExtractor import BaseKGExtractor
from backend.database.neo4j_handler import Neo4jHandler


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterKGExtractor(BaseKGExtractor):
    method_name: KGExtractorTypeEnum = KGExtractorTypeEnum.OPENROUTER

    def __init__(self, neo4j_handler: Neo4jHandler,
                 api_key: Optional[str] = None,
                 model: str = 'qwen/qwen-2.5-72b-instruct'):
        resolved_model = model or os.getenv("KG_OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")
        if not resolved_model:
            raise ValueError(
                "KG_OPENROUTER_MODEL is required for OpenRouter "
                "(e.g. 'anthropic/claude-3.5-haiku', 'meta-llama/llama-3.3-70b-instruct')"
            )

        super().__init__(neo4j_handler, model=resolved_model)

        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")

        default_headers = {}
        referer = os.getenv("OPENROUTER_REFERER")
        title = os.getenv("OPENROUTER_TITLE")
        if referer:
            default_headers["HTTP-Referer"] = referer
        if title:
            default_headers["X-Title"] = title

        try:
            self.client: OpenAI = OpenAI(
                api_key=api_key,
                base_url=OPENROUTER_BASE_URL,
                default_headers=default_headers or None,
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenRouter client: {e}")

        print(f"✓ OpenRouter KG Extractor initialized (model={self.model})")

    def _generate_triplets_json(self, text: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Metinden tripletleri json_object olarak çıkar:\n\n{text}"},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            timeout=120,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenRouter response missing content")
        return content