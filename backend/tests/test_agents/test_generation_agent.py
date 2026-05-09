"""Unit tests for backend/agents/generation_agent.py — pure formatting logic only."""
import pytest
from unittest.mock import MagicMock, patch
from backend.agents.generation_agent import GenerationAgent


@pytest.fixture
def agent():
    with patch("backend.agents.generation_agent.OpenAI"):
        g = GenerationAgent(api_key="fake-key", model="gpt-4o-mini")
    return g


@pytest.fixture
def vector_chunks():
    return [
        {"source_name": "sutdoc", "chunk_text": "Sigorta bedeli yıllık belirlenir.", "similarity": 0.92,
         "section_number": "1.4", "section_title": "Uygulama"},
        {"source_name": "sutdoc", "chunk_text": "Primler aylık ödenir.", "similarity": 0.78,
         "section_number": "1.5", "section_title": "Ödeme"},
    ]


@pytest.fixture
def graph_facts():
    return [
        {"source_entity": "Sigortalı", "target_entity": "Hastane", "relationship": "başvurabilir"},
        {"type": "path", "from": "Sigortalı", "to": "Doktor", "path": []},
    ]


class TestFormatVectorContext:
    @pytest.mark.unit
    def test_empty_returns_no_document_message(self, agent):
        result = agent.format_vector_context([])
        assert "bulunamadı" in result.lower()

    @pytest.mark.unit
    def test_includes_source_name(self, agent, vector_chunks):
        result = agent.format_vector_context(vector_chunks)
        assert "sutdoc" in result

    @pytest.mark.unit
    def test_includes_chunk_text(self, agent, vector_chunks):
        result = agent.format_vector_context(vector_chunks)
        assert "Sigorta bedeli" in result

    @pytest.mark.unit
    def test_max_chunks_limits_output(self, agent, vector_chunks):
        result = agent.format_vector_context(vector_chunks, max_chunks=1)
        assert "Primler aylık ödenir" not in result

    @pytest.mark.unit
    def test_returns_string(self, agent, vector_chunks):
        assert isinstance(agent.format_vector_context(vector_chunks), str)


class TestFormatGraphContext:
    @pytest.mark.unit
    def test_empty_returns_no_info_message(self, agent):
        result = agent.format_graph_context([])
        assert "bulunamadı" in result.lower()

    @pytest.mark.unit
    def test_relationship_format(self, agent, graph_facts):
        result = agent.format_graph_context(graph_facts)
        assert "Sigortalı" in result
        assert "Hastane" in result

    @pytest.mark.unit
    def test_path_type_handled(self, agent, graph_facts):
        result = agent.format_graph_context(graph_facts)
        assert "Doktor" in result

    @pytest.mark.unit
    def test_returns_string(self, agent, graph_facts):
        assert isinstance(agent.format_graph_context(graph_facts), str)


class TestGenerateWithCitations:
    @pytest.mark.unit
    def test_returns_dict_with_answer_and_citations(self, agent, vector_chunks):
        agent.generate_answer = MagicMock(return_value="Yanıt.")
        result = agent.generate_with_citations("soru?", {"vector_context": vector_chunks, "graph_facts": []})
        assert "answer" in result
        assert "citations" in result

    @pytest.mark.unit
    def test_citations_have_section_fields(self, agent, vector_chunks):
        agent.generate_answer = MagicMock(return_value="Yanıt.")
        result = agent.generate_with_citations("soru?", {"vector_context": vector_chunks, "graph_facts": []})
        for citation in result["citations"]:
            assert "section_number" in citation
            assert "section_title" in citation

    @pytest.mark.unit
    def test_citations_max_three(self, agent):
        many_chunks = [
            {"source_name": f"doc{i}", "chunk_text": "text", "similarity": 0.5,
             "section_number": str(i), "section_title": f"Title {i}"}
            for i in range(10)
        ]
        agent.generate_answer = MagicMock(return_value="Yanıt.")
        result = agent.generate_with_citations("soru?", {"vector_context": many_chunks, "graph_facts": []})
        assert len(result["citations"]) <= 3

    @pytest.mark.unit
    def test_empty_context_returns_empty_citations(self, agent):
        agent.generate_answer = MagicMock(return_value="Yanıt.")
        result = agent.generate_with_citations("soru?", {"vector_context": [], "graph_facts": []})
        assert result["citations"] == []
