"""Unit tests for backend/agents/query_preprocessor.py"""
import pytest
from backend.agents.query_preprocessor import QueryPreprocessor


@pytest.fixture
def pp():
    return QueryPreprocessor()


class TestNormalizeWhitespace:
    @pytest.mark.unit
    def test_collapses_spaces(self, pp):
        assert pp.normalize_whitespace("hello   world") == "hello world"

    @pytest.mark.unit
    def test_strips_leading_trailing(self, pp):
        assert pp.normalize_whitespace("  hello  ") == "hello"

    @pytest.mark.unit
    def test_collapses_tabs_and_newlines(self, pp):
        assert pp.normalize_whitespace("hello\t\nworld") == "hello world"

    @pytest.mark.unit
    def test_empty_string(self, pp):
        assert pp.normalize_whitespace("") == ""

    @pytest.mark.unit
    def test_no_change_needed(self, pp):
        assert pp.normalize_whitespace("normal text") == "normal text"


class TestFixTypos:
    @pytest.mark.unit
    def test_sigota_corrected(self, pp):
        assert pp.fix_typos("sigota") == "sigorta"

    @pytest.mark.unit
    def test_hastahane_corrected(self, pp):
        assert pp.fix_typos("hastahane") == "hastane"

    @pytest.mark.unit
    def test_recete_corrected(self, pp):
        assert pp.fix_typos("recete") == "reçete"

    @pytest.mark.unit
    def test_unknown_word_unchanged(self, pp):
        assert pp.fix_typos("doktor") == "doktor"

    @pytest.mark.unit
    def test_multiple_words(self, pp):
        result = pp.fix_typos("hastahane ameliyet recete")
        assert result == "hastane ameliyat reçete"

    @pytest.mark.unit
    def test_case_insensitive(self, pp):
        result = pp.fix_typos("HASTAHANE")
        assert result == "hastane"

    @pytest.mark.unit
    def test_empty_string(self, pp):
        assert pp.fix_typos("") == ""

    @pytest.mark.unit
    def test_mixed_correct_incorrect(self, pp):
        result = pp.fix_typos("sigorta hastahane")
        assert result == "sigorta hastane"


class TestPreprocess:
    @pytest.mark.unit
    def test_full_pipeline(self, pp):
        result = pp.preprocess("  hastahane   ameliyet  ")
        assert result == "hastane ameliyat"

    @pytest.mark.unit
    def test_no_changes(self, pp):
        result = pp.preprocess("hastane")
        assert result == "hastane"
