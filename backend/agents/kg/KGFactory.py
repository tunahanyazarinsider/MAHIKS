"""Factory for KG extractors. Selects a provider based on KG_EXTRACTION_METHOD."""
import os
from typing import Optional

from backend.config import Config
from backend.agents.kg.KGExtractor import BaseKGExtractor
from backend.database.neo4j_handler import Neo4jHandler


class KGFactory:
    @staticmethod
    def create_kg_extractor(method: Optional[str] = None,
                            neo4j_handler: Optional[Neo4jHandler] = None,
                            **kwargs) -> BaseKGExtractor:
        """
        Build the KG extractor specified by `method` (or the KG_EXTRACTION_METHOD env var).

        Supported methods: "ollama" (alias "local"), "gemini", "vertex", "openrouter".
        Provider SDKs are imported lazily so an unused provider never blocks startup.

        If `neo4j_handler` is not provided, one is built from Config.
        Extra kwargs (e.g. model="...", api_key="...") are forwarded to the chosen extractor.
        """
        extractor_type: str = (method or os.getenv("KG_EXTRACTION_METHOD", "ollama")).lower()

        if neo4j_handler is None:
            neo4j_handler = Neo4jHandler(
                Config.NEO4J_URI,
                Config.NEO4J_USER,
                Config.NEO4J_PASSWORD,
            )

        if extractor_type in ("ollama", "local"):
            from backend.agents.kg.OllamaKGExtractor import OllamaKGExtractor
            return OllamaKGExtractor(neo4j_handler, **kwargs)
        if extractor_type == "gemini":
            from backend.agents.kg.GeminiKGExtractor import GeminiKGExtractor
            return GeminiKGExtractor(neo4j_handler, **kwargs)
        if extractor_type == "vertex":
            from backend.agents.kg.VertexKGExtractor import VertexKGExtractor
            return VertexKGExtractor(neo4j_handler, **kwargs)
        if extractor_type == "openrouter":
            from backend.agents.kg.OpenRouterKGExtractor import OpenRouterKGExtractor
            return OpenRouterKGExtractor(neo4j_handler, **kwargs)

        raise ValueError(
            f"Unsupported KG Extractor type: {extractor_type!r}. "
            f"Expected one of: ollama, gemini, vertex, openrouter."
        )
