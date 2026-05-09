"""Unit tests for backend/agents/kg/KGExtractor.py"""
import json
import pytest
from unittest.mock import MagicMock, patch
from backend.agents.kg.KGExtractor import KGExtractor, Triplet


@pytest.fixture
def extractor(mock_llm_client, mock_neo4j):
    return KGExtractor(mock_llm_client, mock_neo4j)


class TestExtractTriplets:
    @pytest.mark.unit
    def test_valid_json_returns_triplets(self, extractor, mock_llm_client):
        mock_llm_client.chat_json.return_value = json.dumps({
            "triplets": [
                {"subject": "Sigortalı", "predicate": "COVERS", "object": "Hastane"},
                {"subject": "SGK", "predicate": "PAYS_FOR", "object": "İlaç"},
            ]
        })
        result = extractor._extract_triplets("some text")
        assert len(result) == 2
        assert result[0].subject == "Sigortalı"
        assert result[0].predicate == "COVERS"

    @pytest.mark.unit
    def test_malformed_json_returns_empty(self, extractor, mock_llm_client):
        mock_llm_client.chat_json.return_value = "not json"
        result = extractor._extract_triplets("text", retries=1)
        assert result == []

    @pytest.mark.unit
    def test_missing_triplets_key_returns_empty(self, extractor, mock_llm_client):
        mock_llm_client.chat_json.return_value = json.dumps({"other": []})
        result = extractor._extract_triplets("text")
        assert result == []

    @pytest.mark.unit
    def test_incomplete_triplet_skipped(self, extractor, mock_llm_client):
        mock_llm_client.chat_json.return_value = json.dumps({
            "triplets": [
                {"subject": "X"},  # missing predicate and object
            ]
        })
        result = extractor._extract_triplets("text")
        assert result == []


class TestPopulateGraph:
    @pytest.mark.unit
    def test_inserts_triplets_to_neo4j(self, extractor, mock_llm_client, mock_neo4j):
        mock_llm_client.chat_json.return_value = json.dumps({
            "triplets": [
                {"subject": "Sigortalı", "predicate": "COVERS", "object": "Hastane"},
            ]
        })
        count = extractor._populate_graph("short text", chunk_size=10000)
        assert count == 1
        mock_neo4j.batch_create_triplets.assert_called_once()

    @pytest.mark.unit
    def test_deduplicates_identical_triplets(self, extractor, mock_llm_client, mock_neo4j):
        same_triplet = {"subject": "Sigortalı", "predicate": "COVERS", "object": "Hastane"}
        mock_llm_client.chat_json.return_value = json.dumps({
            "triplets": [same_triplet, same_triplet]
        })
        count = extractor._populate_graph("short text", chunk_size=10000)
        assert count == 1

    @pytest.mark.unit
    def test_short_entities_filtered(self, extractor, mock_llm_client, mock_neo4j):
        mock_llm_client.chat_json.return_value = json.dumps({
            "triplets": [
                {"subject": "AB", "predicate": "HAS", "object": "CD"},  # len <= 2
            ]
        })
        count = extractor._populate_graph("text", chunk_size=10000)
        assert count == 0
        mock_neo4j.batch_create_triplets.assert_not_called()


class TestTripletModel:
    @pytest.mark.unit
    def test_triplet_creation(self):
        t = Triplet(subject="SGK", predicate="COVERS", object="Ameliyat")
        assert t.subject == "SGK"

    @pytest.mark.unit
    def test_triplet_requires_all_fields(self):
        from pydantic import ValidationError as PydanticValidationError
        with pytest.raises(PydanticValidationError):
            Triplet(subject="SGK")
