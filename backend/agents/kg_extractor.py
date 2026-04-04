"""
Unified Knowledge Graph Extractor for MAHIKS-TR
Facade that selects between local Ollama and Gemini-based extraction.
"""
from typing import Dict, Callable, Optional
import os
import importlib


def _import_local_extractor():
    """Import LocalKGExtractor with fallback for different path setups."""
    try:
        from backend.agents.local_kg_extractor import LocalKGExtractor
        return LocalKGExtractor
    except ImportError:
        from agents.local_kg_extractor import LocalKGExtractor
        return LocalKGExtractor


def _import_gemini_extractor():
    """Import LLMKnowledgeGraphExtractor with fallback for different path setups."""
    try:
        from backend.agents.llm_kg_extractor import LLMKnowledgeGraphExtractor
        return LLMKnowledgeGraphExtractor
    except ImportError:
        from agents.llm_kg_extractor import LLMKnowledgeGraphExtractor
        return LLMKnowledgeGraphExtractor


class KGExtractor:
    """Unified KG extraction interface.
    Uses local Ollama by default, falls back to Gemini if configured."""

    def __init__(self, neo4j_handler, method: str = None, gemini_api_key: str = None):
        """
        Initialize KG extractor with the specified method.

        Args:
            neo4j_handler: Instance of Neo4jHandler
            method: Extraction method - "local" (default), "gemini", or "auto"
            gemini_api_key: Gemini API key (required for "gemini" or "auto" methods)
        """
        self.method = method or os.getenv("KG_EXTRACTION_METHOD", "local")
        self.neo4j = neo4j_handler

        if self.method == "local":
            LocalKGExtractor = _import_local_extractor()
            self.extractor = LocalKGExtractor(neo4j_handler)
            print(f"✓ KG Extractor initialized (method: local/Ollama)")

        elif self.method == "gemini":
            LLMKnowledgeGraphExtractor = _import_gemini_extractor()
            self.extractor = LLMKnowledgeGraphExtractor(neo4j_handler, gemini_api_key)
            print(f"✓ KG Extractor initialized (method: Gemini API)")

        elif self.method == "auto":
            LocalKGExtractor = _import_local_extractor()
            self.local_extractor = LocalKGExtractor(neo4j_handler)
            self.gemini_extractor = None

            api_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if api_key:
                try:
                    LLMKnowledgeGraphExtractor = _import_gemini_extractor()
                    self.gemini_extractor = LLMKnowledgeGraphExtractor(neo4j_handler, api_key)
                except Exception as e:
                    print(f"⚠ Gemini extractor unavailable: {e}")

            print(f"✓ KG Extractor initialized (method: auto)")
        else:
            raise ValueError(f"Unknown KG extraction method: {self.method}")

    def process_document(self, text: str,
                         progress_callback: Callable[[int, int, int], None] = None) -> Dict:
        """
        Process a document and extract knowledge graph triplets.

        For "auto" mode: uses Gemini for small documents (<30K chars, ~10 pages),
        local Ollama for larger documents.

        Args:
            text: Document text
            progress_callback: Optional progress callback

        Returns:
            Statistics dictionary
        """
        if self.method == "auto":
            if len(text) < 30000 and self.gemini_extractor:
                print("    Auto mode: Using Gemini for small document")
                return self.gemini_extractor.process_document(text)
            else:
                print("    Auto mode: Using local Ollama for large document")
                return self.local_extractor.process_document(text, progress_callback)
        else:
            if self.method == "local":
                return self.extractor.process_document(text, progress_callback)
            else:
                return self.extractor.process_document(text)
