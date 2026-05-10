"""Unit tests for backend/agents/retrieval_agent.py"""
import json
import pytest
from unittest.mock import MagicMock, patch
from backend.agents.retrieval_agent import RetrievalAgent


@pytest.fixture
def agent(mock_qdrant, mock_neo4j, mock_mysql):
    with patch("backend.agents.retrieval_agent.spacy") as mock_spacy:
        mock_spacy.load.side_effect = OSError("no model")
        return RetrievalAgent(mock_qdrant, mock_neo4j, mock_mysql)


class TestSplitIntoSubChunks:
    @pytest.mark.unit
    def test_short_text_single_sub_chunk(self, agent):
        result = agent._split_into_sub_chunks("word " * 50, "src", 1, 0.9)
        assert len(result) == 1
        assert result[0]["source_name"] == "src"

    @pytest.mark.unit
    def test_short_text_preserves_section_fields(self, agent):
        result = agent._split_into_sub_chunks(
            "word " * 50, "doc", 1, 0.5,
            section_number="1.2.3", section_title="Test Title"
        )
        assert result[0]["section_number"] == "1.2.3"
        assert result[0]["section_title"] == "Test Title"

    @pytest.mark.unit
    def test_long_text_multiple_sub_chunks(self, agent):
        text = "word " * 500
        result = agent._split_into_sub_chunks(text, "src", 1, 0.8)
        assert len(result) > 1

    @pytest.mark.unit
    def test_sub_chunks_have_required_keys(self, agent):
        result = agent._split_into_sub_chunks("word " * 50, "src", 1, 0.5)
        for sc in result:
            assert "chunk_text" in sc
            assert "source_name" in sc
            assert "similarity" in sc
            assert "section_number" in sc
            assert "section_title" in sc

    @pytest.mark.unit
    def test_section_fields_default_empty(self, agent):
        result = agent._split_into_sub_chunks("word " * 50, "src", 1, 0.5)
        assert result[0]["section_number"] == ""
        assert result[0]["section_title"] == ""


class TestVectorSearchMetadataParsing:
    @pytest.mark.unit
    def test_metadata_json_parsed_into_chunk(self, agent, mock_mysql, mock_qdrant):
        mock_qdrant.query_with_scores.return_value = [{"chunk_id": 1, "similarity": 0.9, "distance": 0.1}]
        mock_mysql.get_chunks_by_ids.return_value = [{
            "id": 1,
            "chunk_text": "test",
            "source_name": "sutdoc",
            "metadata_json": json.dumps({"section_number": "1.2", "section_title": "Kapsam"})
        }]
        results = agent.vector_search("query")
        assert results[0]["section_number"] == "1.2"
        assert results[0]["section_title"] == "Kapsam"

    @pytest.mark.unit
    def test_missing_metadata_json_graceful(self, agent, mock_mysql, mock_qdrant):
        mock_qdrant.query_with_scores.return_value = [{"chunk_id": 1, "similarity": 0.9, "distance": 0.1}]
        mock_mysql.get_chunks_by_ids.return_value = [{
            "id": 1,
            "chunk_text": "test",
            "source_name": "sutdoc",
            "metadata_json": None
        }]
        results = agent.vector_search("query")
        assert results[0]["source_name"] == "sutdoc"

    @pytest.mark.unit
    def test_no_results_returns_empty(self, agent, mock_qdrant):
        mock_qdrant.query_with_scores.return_value = []
        results = agent.vector_search("query")
        assert results == []
