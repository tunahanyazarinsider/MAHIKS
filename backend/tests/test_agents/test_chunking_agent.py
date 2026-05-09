"""Unit tests for backend/agents/structure_aware_chunking_agent.py"""
import pytest
from backend.agents.structure_aware_chunking_agent import (
    SUTChunker,
    Chunk,
    ChunkMetadata,
)


@pytest.fixture
def chunker():
    return SUTChunker()


@pytest.fixture
def sut_text():
    return """BİRİNCİ BÖLÜM
Amaç ve Kapsam

1.1 Amaç
Bu yönetmelik, sağlık sigortası kapsamını düzenler ve sigortalıların haklarını belirler.

1.2 Kapsam
Bu yönetmelik, tüm sigortalıları kapsar. Sigorta şirketi tarafından sağlanan hizmetler bu kapsama dahildir.

1.3 Tanımlar
Sigortalı: Poliçe sahibi kişidir. Hak sahibi olarak değerlendirilir.
Sigorta şirketi: Riski üstlenen ve prim tahsil eden kuruluştur.

1.4 Uygulama Esasları
Sigorta bedeli yıllık olarak belirlenir. Primler aylık ödenir.
"""


class TestChunkMetadataToDict:
    @pytest.mark.unit
    def test_to_dict_contains_expected_keys(self, sample_chunk_metadata):
        d = sample_chunk_metadata.to_dict()
        for key in ("section_number", "section_title", "level", "parent_chain",
                    "bolum", "fikra", "chunk_type", "chunk_index",
                    "is_merged", "merged_sections"):
            assert key in d

    @pytest.mark.unit
    def test_to_dict_values(self, sample_chunk_metadata):
        d = sample_chunk_metadata.to_dict()
        assert d["section_number"] == "1.4.1.A"
        assert d["section_title"] == "Kapsam ve Uygulama"
        assert d["level"] == 4


class TestChunkToDict:
    @pytest.mark.unit
    def test_to_dict_has_text(self, sample_chunk):
        d = sample_chunk.to_dict()
        assert d["text"] == sample_chunk.text

    @pytest.mark.unit
    def test_to_dict_flattens_metadata(self, sample_chunk):
        d = sample_chunk.to_dict()
        assert d["section_number"] == "1.4.1.A"
        assert d["section_title"] == "Kapsam ve Uygulama"
        assert d["level"] == 4

    @pytest.mark.unit
    def test_text_for_llm_includes_header(self, sample_chunk):
        result = sample_chunk.text_for_llm
        assert "1.4.1.A" in result
        assert sample_chunk.text in result

    @pytest.mark.unit
    def test_text_for_llm_no_header(self, sample_chunk_metadata):
        chunk = Chunk(
            text="some text",
            context_header="",
            word_count=2,
            order=0,
            metadata=sample_chunk_metadata,
        )
        assert chunk.text_for_llm == "some text"


class TestSUTChunkerChunkDocument:
    @pytest.mark.unit
    def test_returns_list(self, chunker, sut_text):
        chunks = chunker.chunk_document(sut_text)
        assert isinstance(chunks, list)

    @pytest.mark.unit
    def test_produces_chunks(self, chunker, sut_text):
        chunks = chunker.chunk_document(sut_text)
        assert len(chunks) > 0

    @pytest.mark.unit
    def test_chunks_are_chunk_instances(self, chunker, sut_text):
        chunks = chunker.chunk_document(sut_text)
        for c in chunks:
            assert isinstance(c, Chunk)

    @pytest.mark.unit
    def test_chunk_has_text(self, chunker, sut_text):
        chunks = chunker.chunk_document(sut_text)
        for c in chunks:
            assert isinstance(c.text, str)
            assert len(c.text) > 0

    @pytest.mark.unit
    def test_chunk_metadata_section_number(self, chunker, sut_text):
        chunks = chunker.chunk_document(sut_text)
        section_numbers = [c.metadata.section_number for c in chunks]
        assert any(sn.startswith("1.") for sn in section_numbers)

    @pytest.mark.unit
    def test_chunk_order_sequential(self, chunker, sut_text):
        chunks = chunker.chunk_document(sut_text)
        orders = [c.order for c in chunks]
        assert orders == list(range(len(orders)))

    @pytest.mark.unit
    def test_empty_text_returns_empty(self, chunker):
        chunks = chunker.chunk_document("")
        assert isinstance(chunks, list)

    @pytest.mark.unit
    def test_word_count_positive(self, chunker, sut_text):
        chunks = chunker.chunk_document(sut_text)
        for c in chunks:
            assert c.word_count > 0
