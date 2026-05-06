"""Factory for KG extractors. Selects a provider based on KG_EXTRACTION_METHOD."""
import os
from typing import Optional

from backend.config import Config
from backend.agents.kg.KGExtractor import KGExtractor
from backend.database.neo4j_handler import Neo4jHandler
from backend.agents.client.BaseLLMClient import BaseLLMClient
from backend.agents.client.factory.LLMClientFactory import LLMClientFactory


class KGFactory:
    @staticmethod
    def create_kg_extractor(method: Optional[str] = None,
                            neo4j_handler: Optional[Neo4jHandler] = None,
                            usage : str = "kg_extraction",
                            **kwargs) -> KGExtractor:
        """
        Build the KG extractor specified by `method` (or the KG_EXTRACTION_METHOD env var).

        Supported methods: "ollama" (alias "local"), "gemini", "vertex", "openrouter".
        Provider SDKs are imported lazily so an unused provider never blocks startup.

        If `neo4j_handler` is not provided, one is built from Config.
        Extra kwargs (e.g. model="...", api_key="...") are forwarded to the chosen extractor.
        """

        if neo4j_handler is None:
            neo4j_handler = Neo4jHandler(
                Config.NEO4J_URI,
                Config.NEO4J_USER,
                Config.NEO4J_PASSWORD,
            )

        llm_client : BaseLLMClient = LLMClientFactory.create_llm_client(
            provider=method,
            usage=usage,
            **kwargs
        )

        kg_extractor : KGExtractor = KGExtractor(llm_client, neo4j_handler)
        return kg_extractor


