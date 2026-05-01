#!/usr/bin/env python3
"""
Vectorize-only script: Extract text, chunk, and embed with BGE-M3.
Skips KG extraction entirely.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / 'backend'))

from backend.database.mysql_handler import MySQLHandler
from backend.database.qdrant_handler import QdrantHandler
from backend.agents.ingestion_agent import IngestionAgent
from backend.agents.extraction_agent import ExtractionAgent
from backend.agents.structure_aware_chunking_agent import SUTChunker, Chunk
from backend.agents.vectorization_agent import VectorizationAgent
from backend.config import Config
from datetime import datetime
from typing import List


def main():
    print("\n" + "=" * 70)
    print("MAHIKS-TR: Vectorize Only (BGE-M3)")
    print("=" * 70)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Embedding model: {Config.EMBEDDING_MODEL}")
    print(f"Data dir: {Config.DATA_DIR}")
    print("=" * 70 + "\n")

    Config.validate()

    # Init databases
    print("Initializing databases...")
    mysql = MySQLHandler(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE
    )
    mysql.create_tables()

    vector = QdrantHandler(
        url=Config.QDRANT_URL,
        api_key=Config.QDRANT_API_KEY,
        collection_name=Config.QDRANT_COLLECTION_NAME,
        embedding_model_name=Config.EMBEDDING_MODEL,
        dense_vector_name=Config.QDRANT_DENSE_VECTOR_NAME,
        sparse_vector_name=Config.QDRANT_SPARSE_VECTOR_NAME,
        sparse_model_name=Config.QDRANT_SPARSE_MODEL,
        sparse_language=Config.QDRANT_SPARSE_LANGUAGE,
        dense_dim=Config.QDRANT_DENSE_DIM,
    )

    # Reset vector store for fresh re-index
    print("\nResetting Qdrant collection for fresh embeddings...")
    vector.reset_collection()

    # Init agents
    ingestion = IngestionAgent(data_directory=Config.DATA_DIR)
    extraction = ExtractionAgent(
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP
    )
    chunking = SUTChunker()
    vectorization = VectorizationAgent(vector, mysql)

    # Scan documents
    print("\n[Phase 1] Scanning documents...")
    documents = ingestion.scan_documents()
    if not documents:
        print("No documents found!")
        sys.exit(1)
    print(f"Found {len(documents)} documents\n")

    stats = {'docs': 0, 'chunks': 0, 'errors': 0}

    for idx, doc in enumerate(documents, 1):
        print(f"[{idx}/{len(documents)}] {doc['name']} ({doc['type']}, {doc['size']:,} bytes)")

        try:
            # Extract text
            text = extraction.extract_text(doc['path'], doc['type'])
            if not text or len(text) < 100:
                print("  Skipping: insufficient text")
                continue

            # Store document
            doc_id = mysql.insert_document(
                source_url=doc['path'],
                source_name=doc['name'],
                doc_type=doc['type'],
                content=text
            )
            if doc_id is None:
                # Document exists, re-vectorize from existing chunks
                print("  Document exists in MySQL, re-vectorizing existing chunks...")
                # Find existing doc ID
                existing = mysql.get_document_by_hash(doc['path'])
                if existing:
                    num_chunks = vectorization.vectorize_document(existing['id'])
                    stats['chunks'] += num_chunks
                    stats['docs'] += 1
                    print(f"  Re-vectorized {num_chunks} chunks")
                continue

            # Chunk and vectorize
            print("  Chunking document with SUT...")
            chunks: List[Chunk] = chunking.chunk_document(text)
            print(f"  {len(chunks)} chunks created")
            num_chunks = vectorization.vectorize_chunks(chunks, doc_id)

            stats['docs'] += 1
            stats['chunks'] += num_chunks
            print(f"  {num_chunks} chunks vectorized\n")

        except Exception as e:
            print(f"  Error: {e}\n")
            stats['errors'] += 1

    print("\n" + "=" * 70)
    print("Done!")
    print(f"Documents: {stats['docs']}/{len(documents)}")
    print(f"Chunks embedded: {stats['chunks']}")
    print(f"Errors: {stats['errors']}")
    print(f"Qdrant points: {vector.get_count()}")
    print(f"End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    mysql.close()


if __name__ == "__main__":
    main()
