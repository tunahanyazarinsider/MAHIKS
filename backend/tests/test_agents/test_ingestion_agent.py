"""Unit tests for backend/agents/ingestion_agent.py"""
import pytest
from pathlib import Path
from unittest.mock import patch
from backend.agents.ingestion_agent import IngestionAgent


@pytest.fixture
def tmp_doc_dir(tmp_path):
    (tmp_path / "report.pdf").write_bytes(b"%PDF content")
    (tmp_path / "article.html").write_text("<html><body>text</body></html>", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("Some notes", encoding="utf-8")
    (tmp_path / "ignored.xyz").write_text("bad file", encoding="utf-8")
    return tmp_path


@pytest.fixture
def agent(tmp_doc_dir):
    return IngestionAgent(data_directory=str(tmp_doc_dir))


class TestScanDocuments:
    @pytest.mark.unit
    def test_returns_list(self, agent):
        docs = agent.scan_documents()
        assert isinstance(docs, list)

    @pytest.mark.unit
    def test_finds_pdf(self, agent):
        docs = agent.scan_documents()
        names = [d["name"] for d in docs]
        assert "report" in names

    @pytest.mark.unit
    def test_finds_html(self, agent):
        docs = agent.scan_documents()
        names = [d["name"] for d in docs]
        assert "article" in names

    @pytest.mark.unit
    def test_finds_txt(self, agent):
        docs = agent.scan_documents()
        names = [d["name"] for d in docs]
        assert "notes" in names

    @pytest.mark.unit
    def test_ignores_unknown_extension(self, agent):
        docs = agent.scan_documents()
        names = [d["name"] for d in docs]
        assert "ignored" not in names

    @pytest.mark.unit
    def test_doc_dict_has_required_keys(self, agent):
        docs = agent.scan_documents()
        for doc in docs:
            assert "name" in doc
            assert "path" in doc
            assert "type" in doc
            assert "size" in doc

    @pytest.mark.unit
    def test_empty_dir_returns_empty(self, tmp_path):
        agent = IngestionAgent(data_directory=str(tmp_path))
        docs = agent.scan_documents()
        assert docs == []
