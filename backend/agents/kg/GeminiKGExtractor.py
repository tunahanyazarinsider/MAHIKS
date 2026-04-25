"""Gemini Developer API KG extractor."""
import os
from typing import Optional

from google import genai

from backend.agents.kg.KGExtractor import BaseKGExtractor, KG_JSON_SCHEMA
from backend.database.neo4j_handler import Neo4jHandler


class GeminiKGExtractor(BaseKGExtractor):
    method_name = "Gemini"

    def __init__(self, neo4j_handler: Neo4jHandler,
                 api_key: Optional[str] = None,
                 model: Optional[str] = None):
        super().__init__(
            neo4j_handler,
            model=model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        )
        api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not found in environment variables")

        try:
            self.client: genai.Client = genai.Client(api_key=api_key)
        except Exception as e:
            raise ValueError(f"Failed to initialize Gemini client: {e}")

        print(f"✓ Gemini KG Extractor initialized (model={self.model})")

    def _generate_triplets_json(self, text: str) -> str:
        prompt = f"{self.system_prompt}\n\n---\n\nMetinden tripletleri çıkar:\n\n{text}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": KG_JSON_SCHEMA,
            },
        )
        return response.text
