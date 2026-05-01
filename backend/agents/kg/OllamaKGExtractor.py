"""Ollama (local) KG extractor."""
import os
from typing import Optional

import requests

from backend.agents.kg import KGExtractorTypeEnum
from backend.agents.kg.KGExtractor import BaseKGExtractor
from backend.database.neo4j_handler import Neo4jHandler


class OllamaKGExtractor(BaseKGExtractor):
    
    method_name: KGExtractorTypeEnum = KGExtractorTypeEnum.OLLAMA

    def __init__(self, neo4j_handler: Neo4jHandler,
                 base_url: Optional[str] = None,
                 model: Optional[str] = None):
        super().__init__(
            neo4j_handler,
            model=model or os.getenv("KG_OLLAMA_MODEL", "qwen2.5:7b"),
        )
        self.base_url: str = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

        try:
            response: requests.Response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"✓ Local KG Extractor initialized (Ollama, model={self.model})")
            else:
                print(f"⚠ Warning: Could not connect to Ollama at {self.base_url}")
        except Exception as e:
            print(f"⚠ Warning: Ollama connection test failed: {e}")

    def _generate_triplets_json(self, text: str) -> str:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Metinden tripletleri çıkar:\n\n{text}"},
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2000,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "")
