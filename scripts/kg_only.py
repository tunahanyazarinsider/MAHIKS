#!/usr/bin/env python3
"""

KG-only script: Extract text from files and feed it to the KG extractor.
Refuses to run if Qdrant has no embeddings — KG is only built on top of
already-embedded documents (run vectorize_only.py first).
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / 'backend'))


from backend.agents.kg.KGExtractor import KGExtractor
from backend.agents.kg.KGFactory import KGFactory
from backend.database.neo4j_handler import Neo4jHandler
from backend.database.qdrant_handler import QdrantHandler
from backend.agents.ingestion_agent import IngestionAgent
from backend.agents.extraction_agent import ExtractionAgent
from backend.config import Config
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Rebuild Neo4j knowledge graph from documents"
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Clear all Neo4j data before processing (WARNING: deletes all nodes/relationships)'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default=Config.DATA_DIR,
        help='Directory containing documents to process'
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("MAHIKS-TR: KG Only (Neo4j Triplet Extraction)")
    print("=" * 70)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"KG method: {Config.KG_EXTRACTION_METHOD}")
    print(f"Data dir: {args.data_dir}")
    print("=" * 70 + "\n")

    Config.validate()

    # Guard: refuse to run if no embeddings exist yet
    print("Checking Qdrant for existing embeddings...")
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
    point_count = vector.get_count()
    if point_count == 0:
        print(f"✗ Qdrant collection '{Config.QDRANT_COLLECTION_NAME}' is empty.")
        print("  Run scripts/vectorize_only.py first to embed documents.")
        sys.exit(1)
    print(f"✓ Qdrant has {point_count} points — proceeding with KG extraction\n")

    # Init Neo4j
    print("Initializing Neo4j...")
    neo4j = Neo4jHandler(
        uri=Config.NEO4J_URI,
        user=Config.NEO4J_USER,
        password=Config.NEO4J_PASSWORD
    )
    neo4j.create_indexes()

    if args.reset:

        print("⚠ WARNING: Resetting Neo4j graph!")
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            neo4j.clear_all()
            print("✓ Neo4j cleared\n")
        else:
            print("Reset cancelled")
            sys.exit(0)


    print("Initializing agents...")
    ingestion = IngestionAgent(data_directory=args.data_dir)
    extraction = ExtractionAgent(
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP
    )

    kg_extractor: KGExtractor = KGFactory.create_kg_extractor(
        method=Config.KG_EXTRACTION_METHOD,
        neo4j_handler=neo4j
    )

    # LLM connectivity check
    try:
        print("Testing LLM connectivity with kg_extractor...")
        response = kg_extractor.process_document(
            "Test document for connectivity check. This should be a simple "
            "sentence to verify that the LLM client is working correctly."
        )
        print("✓ LLM connectivity OK\n")
        print(f"Test LLM Response: {response})
    except Exception as e:
        print(f"✗ LLM connectivity test failed: {e}")
        sys.exit(1)

    # Scan documents
    print("[Phase 1] Scanning documents...")

    documents = ingestion.scan_documents()
    if not documents:
        print("No documents found!")
        sys.exit(1)
    print(f"Found {len(documents)} documents\n")

    stats = {'docs': 0, 'triplets': 0, 'errors': 0}

    for idx, doc in enumerate(documents, 1):
        print(f"[{idx}/{len(documents)}] {doc['name']} ({doc['type']}, {doc['size']:,} bytes)")

        try:
            text = extraction.extract_text(doc['path'], doc['type'])
            if not text or len(text) < 100:
                print("  Skipping: insufficient text")
                continue

            print("  Extracting knowledge graph...")
            kg_stats = kg_extractor.process_document(text)
            triplets = kg_stats.get('triplets_extracted', 0)

            stats['docs'] += 1
            stats['triplets'] += triplets
            print(f"  {triplets} triplets extracted\n")

        except Exception as e:
            print(f"  Error: {e}\n")
            stats['errors'] += 1

    # Final stats
    print("=" * 70)
    print("Done!")
    print(f"Documents: {stats['docs']}/{len(documents)}")
    print(f"Triplets extracted: {stats['triplets']}")
    print(f"Errors: {stats['errors']}")
    graph_stats = neo4j.get_statistics()
    print(f"Neo4j Nodes: {graph_stats.get('node_count', 0)}")
    print(f"Neo4j Relationships: {graph_stats.get('relationship_count', 0)}")
    print(f"End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    neo4j.close()

    sys.exit(1 if stats['errors'] > 0 else 0)


if __name__ == "__main__":
    main()
