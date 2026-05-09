"""
Shared fixtures for MAHIKS backend test suite.
"""
import os
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock

# Structure-aware chunker imports `from config import Config` (backend-root style),
# so we add both repo root and backend/ to sys.path.
_REPO_ROOT = str(Path(__file__).parent.parent.parent)
_BACKEND_ROOT = str(Path(__file__).parent.parent)
for _p in (_REPO_ROOT, _BACKEND_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.agents.structure_aware_chunking_agent import Chunk, ChunkMetadata

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-unit-tests")
os.environ.setdefault("MYSQL_PASSWORD", "testpass")
os.environ.setdefault("NEO4J_PASSWORD", "testpass")


@pytest.fixture
def mock_mysql():
    db = MagicMock()
    db.get_chunks_by_ids.return_value = []
    db.insert_chunk.return_value = 1
    db.insert_document.return_value = 1
    return db


@pytest.fixture
def mock_qdrant():
    q = MagicMock()
    q.query_with_scores.return_value = []
    q.add_chunks.return_value = None
    q.get_count.return_value = 0
    return q


@pytest.fixture
def mock_neo4j():
    n = MagicMock()
    n.query_related_entities.return_value = []
    n.find_path.return_value = None
    n.batch_create_triplets.return_value = None
    n.get_statistics.return_value = {"node_count": 0, "relationship_count": 0}
    return n


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.chat.return_value = "mock LLM response"
    return client


@pytest.fixture
def sample_chunk_metadata():
    return ChunkMetadata(
        section_number="1.4.1.A",
        section_title="Kapsam ve Uygulama",
        level=4,
        parent_chain=["1", "1.4", "1.4.1"],
        bolum="BİRİNCİ BÖLÜM",
        fikra=None,
        chunk_type="full_section",
        chunk_index=0,
    )


@pytest.fixture
def sample_chunk(sample_chunk_metadata):
    return Chunk(
        text="Bu bölüm sağlık sigortası kapsamını düzenlemektedir.",
        context_header="1.4.1.A — Kapsam ve Uygulama",
        word_count=7,
        order=0,
        metadata=sample_chunk_metadata,
    )


@pytest.fixture
def sample_sut_text():
    return """BİRİNCİ BÖLÜM
Amaç ve Kapsam

1.1 Amaç
Bu yönetmelik, sağlık sigortası kapsamını düzenler.

1.2 Kapsam
Yönetmelik, tüm sigortalıları kapsar.

1.3 Tanımlar
Sigortalı: Poliçe sahibi kişidir.
Sigorta şirketi: Riski üstlenen kuruluştur.

1.4 Uygulama Esasları
Sigorta bedeli yıllık olarak belirlenir.
"""


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_user_repository():
    repo = MagicMock()
    repo.get_by_email.return_value = None
    repo.exists_by_email.return_value = False
    repo.create_user.return_value = None
    repo.get_by_id.return_value = None
    return repo
