"""Unit tests for backend/agents/GenerationAgent.py (provider-agnostic, the active agent)."""
import pytest
from unittest.mock import MagicMock

from backend.agents.GenerationAgent import GenerationAgent


@pytest.fixture
def agent(mock_llm_client):
    return GenerationAgent(mock_llm_client)


@pytest.fixture
def vector_chunks():
    return [
        {"source_name": "sutdoc", "chunk_text": "Sigorta bedeli yıllık belirlenir.",
         "similarity": 0.92, "section_number": "1.4", "section_title": "Uygulama"},
        {"source_name": "sutdoc", "chunk_text": "Primler aylık ödenir.",
         "similarity": 0.78, "section_number": "1.5", "section_title": "Ödeme"},
    ]


class TestSystemPromptCitationContract:
    @pytest.mark.unit
    def test_prompt_demonstrates_concrete_citation_numbers(self, agent, vector_chunks):
        """The prompt must show literal example numbers — small models
        otherwise copy the placeholder symbol (e.g. produce "[N]") verbatim."""
        messages = agent.build_messages(
            "soru?",
            {"vector_context": vector_chunks, "graph_facts": []},
        )
        system_content = messages[0]["content"]
        assert messages[0]["role"] == "system"
        # Concrete numbers, not abstract placeholder.
        assert "[1]" in system_content
        assert "[2]" in system_content
        # Worked example must be present.
        assert "DOĞRU ÖRNEK" in system_content
        assert "YANLIŞ ÖRNEK" in system_content
        # Header for the numbered source list.
        assert "Numaralı Kaynaklar" in system_content
        # Explicit ban on placeholder symbols (the model should be told NOT to write "N").
        assert "ASLA" in system_content

    @pytest.mark.unit
    def test_chunks_are_numbered_in_prompt(self, agent, vector_chunks):
        messages = agent.build_messages(
            "soru?",
            {"vector_context": vector_chunks, "graph_facts": []},
        )
        system_content = messages[0]["content"]
        assert "Kaynak 1" in system_content
        assert "Kaynak 2" in system_content


class TestGenerateWithCitationsIndex:
    @pytest.mark.unit
    def test_citations_carry_sequential_index(self, agent, vector_chunks):
        agent.generate_answer = MagicMock(return_value="Yanıt [1][2].")
        result = agent.generate_with_citations(
            "soru?", {"vector_context": vector_chunks, "graph_facts": []},
        )
        indexes = [c["index"] for c in result["citations"]]
        assert indexes == [1, 2]

    @pytest.mark.unit
    def test_citations_include_up_to_ten_chunks(self, agent):
        many_chunks = [
            {"source_name": f"doc{i}", "chunk_text": "text", "similarity": 0.5,
             "section_number": str(i), "section_title": f"Title {i}"}
            for i in range(15)
        ]
        agent.generate_answer = MagicMock(return_value="Yanıt.")
        result = agent.generate_with_citations(
            "soru?", {"vector_context": many_chunks, "graph_facts": []},
        )
        # Cap is 10 (matches the chunk window shown to the LLM).
        assert len(result["citations"]) == 10
        assert result["citations"][0]["index"] == 1
        assert result["citations"][-1]["index"] == 10

    @pytest.mark.unit
    def test_citation_has_required_frontend_fields(self, agent, vector_chunks):
        agent.generate_answer = MagicMock(return_value="Yanıt.")
        result = agent.generate_with_citations(
            "soru?", {"vector_context": vector_chunks, "graph_facts": []},
        )
        c = result["citations"][0]
        for key in ("index", "source", "section_number", "section_title",
                    "content", "document_type", "relevance_score"):
            assert key in c, f"citation missing key {key}"

    @pytest.mark.unit
    def test_empty_context_returns_no_citations(self, agent):
        agent.generate_answer = MagicMock(return_value="Yanıt.")
        result = agent.generate_with_citations(
            "soru?", {"vector_context": [], "graph_facts": []},
        )
        assert result["citations"] == []
