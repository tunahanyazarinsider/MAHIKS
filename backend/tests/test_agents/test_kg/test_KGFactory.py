"""Unit tests for backend/agents/kg/KGFactory.py"""
import pytest
from unittest.mock import MagicMock, patch
from backend.agents.kg.KGExtractor import KGExtractor


class TestKGFactoryDispatch:
    @pytest.mark.unit
    def test_returns_kg_extractor_instance(self, mock_neo4j):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        with patch("backend.agents.kg.KGFactory.LLMClientFactory") as mock_factory:
            mock_factory.create_llm_client.return_value = mock_llm
            from backend.agents.kg.KGFactory import KGFactory
            extractor = KGFactory.create_kg_extractor(method="ollama", neo4j_handler=mock_neo4j)
        assert isinstance(extractor, KGExtractor)

    @pytest.mark.unit
    def test_creates_neo4j_if_none_provided(self):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        with patch("backend.agents.kg.KGFactory.LLMClientFactory") as mock_factory, \
             patch("backend.agents.kg.KGFactory.Neo4jHandler") as mock_handler:
            mock_factory.create_llm_client.return_value = mock_llm
            mock_handler.return_value = MagicMock()
            from backend.agents.kg.KGFactory import KGFactory
            KGFactory.create_kg_extractor(method="ollama", neo4j_handler=None)
            mock_handler.assert_called_once()

    @pytest.mark.unit
    def test_uses_provided_neo4j(self, mock_neo4j):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        with patch("backend.agents.kg.KGFactory.LLMClientFactory") as mock_factory, \
             patch("backend.agents.kg.KGFactory.Neo4jHandler") as mock_handler:
            mock_factory.create_llm_client.return_value = mock_llm
            from backend.agents.kg.KGFactory import KGFactory
            extractor = KGFactory.create_kg_extractor(method="ollama", neo4j_handler=mock_neo4j)
            mock_handler.assert_not_called()
            assert extractor.neo4j is mock_neo4j
