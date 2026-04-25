#!/usr/bin/env python3
"""
Knowledge Base Update Script for MAHIKS-TR
Run this script to process documents and update all databases
"""
import sys
from pathlib import Path
from typing import List

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
# with the above, now this script will be callable like:
# python3 -m backend.scripts.update_knowledge_base

from backend.agents.kg.KGExtractor import BaseKGExtractor
from backend.agents.kg.KGFactory import KGFactory
from backend.database.mysql_handler import MySQLHandler
from backend.database.chroma_handler import ChromaDBHandler
from backend.database.neo4j_handler import Neo4jHandler
from backend.database.bm25_handler import BM25Handler
from backend.agents.ingestion_agent import IngestionAgent
from backend.agents.extraction_agent import ExtractionAgent
from backend.agents.structure_aware_chunking_agent import SUTChunker, Chunk
from backend.agents.vectorization_agent import VectorizationAgent
from backend.config import Config
import argparse
from datetime import datetime


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="Update MAHIKS-TR knowledge base from documents"
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset all databases before processing (WARNING: deletes all data)'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default=Config.DATA_DIR,
        help='Directory containing documents to process'
    )

    # to process a file named "new_docs" in "/data", run:
    # python3 -m backend.scripts.update_knowledge_base --data-dir /data/raw_documents/pdf_data_1.pdf

    args = parser.parse_args()

    print("\n" + "="*70)
    print("MAHIKS-TR Knowledge Base Update")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data directory: {args.data_dir}")
    print("="*70 + "\n")

    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        sys.exit(1)

    # Initialize database handlers
    print("Initializing databases...")
    try:
        mysql = MySQLHandler(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE
        )
        mysql.create_tables()

        chroma = ChromaDBHandler(
            persist_directory=Config.CHROMA_PERSIST_DIR,
            collection_name=Config.CHROMA_COLLECTION_NAME,
            embedding_model_name=Config.EMBEDDING_MODEL
        )

        neo4j = Neo4jHandler(
            uri=Config.NEO4J_URI,
            user=Config.NEO4J_USER,
            password=Config.NEO4J_PASSWORD
        )
        neo4j.create_indexes()

        bm25 = BM25Handler(
            persist_directory=Config.BM25_PERSIST_DIR,
            k1=Config.BM25_K1,
            b=Config.BM25_B
        )

    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        sys.exit(1)

    # Reset databases if requested
    if args.reset:
        print("\n⚠ WARNING: Resetting all databases!")
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            print("Resetting databases...")
            chroma.reset_collection()
            neo4j.clear_all()
            bm25.reset_index()
            print("✓ Databases reset")
        else:
            print("Reset cancelled")
            sys.exit(0)

    # Initialize agents
    print("\nInitializing agents...")
    print(f"Knowledge Graph Method: {Config.KG_EXTRACTION_METHOD}")
    try:
        ingestion = IngestionAgent(data_directory=args.data_dir)
        extraction = ExtractionAgent(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP
        )

        chunking = SUTChunker()

        vectorization = VectorizationAgent(chroma, mysql, bm25)

        # Initialize KG extractor (local Ollama by default, Gemini as option)
        kg_extractor : BaseKGExtractor = KGFactory.create_kg_extractor(method=Config.KG_EXTRACTION_METHOD, neo4j_handler=neo4j)

    except Exception as e:
        print(f"✗ Agent initialization failed: {e}")
        sys.exit(1)

    # Scan for documents
    print("\n" + "="*70)
    print("Phase 1: Document Discovery")
    print("="*70)
    documents = ingestion.scan_documents()

    if not documents:
        print("✗ No documents found!")
        print(f"  Please add PDF, HTML, or TXT files to: {args.data_dir}")
        sys.exit(1)

    print(f"Found {len(documents)} documents to process\n")

    # Process each document
    stats = {
        'documents_processed': 0,
        'chunks_created': 0,
        'triplets_extracted': 0,
        'errors': 0
    }

    print("="*70)
    print("Phase 2: Document Processing")
    print("="*70 + "\n")

    for idx, doc in enumerate(documents, 1):
        print(f"[{idx}/{len(documents)}] Processing: {doc['name']}")
        print(f"  Type: {doc['type']}, Size: {doc['size']:,} bytes")

        try:
            # Extract text
            print(f"  [1/4] Extracting text...")
            text = extraction.extract_text(doc['path'], doc['type'])

            if not text or len(text) < 100:
                print(f"  ⚠ Skipping: Insufficient text content")
                continue

            # Insert document into MySQL
            print(f"  [2/4] Storing document metadata...")
            doc_id = mysql.insert_document(
                source_url=doc['path'],
                source_name=doc['name'],
                doc_type=doc['type'],
                content=text
            )

            if doc_id is None:
                print(f"  ⚠ Document already exists, skipping...")
                continue

            # Create chunks
            print(f"  [3/4] Creating text chunks...")
            chunks: List[Chunk] = chunking.chunk_document(text)

            # Vectorize chunks
            print(f"  [4/4] Vectorizing and storing chunks...")
            num_chunks = vectorization.vectorize_chunks(chunks, doc_id)

            # Extract knowledge graph triplets
            print(f"  [4/4] Extracting knowledge graph...")
            kg_stats = kg_extractor.process_document(text)
            triplets_count = kg_stats.get('triplets_extracted', 0)

            # Update stats
            stats['documents_processed'] += 1
            stats['chunks_created'] += num_chunks
            stats['triplets_extracted'] += triplets_count

            print(f"  ✓ Complete: {num_chunks} chunks, "
                  f"{triplets_count} triplets\n")

        except Exception as e:
            print(f"  ✗ Error processing document: {e}\n")
            stats['errors'] += 1
            continue

    # Final statistics
    print("="*70)
    print("Processing Complete")
    print("="*70)
    print(f"Documents processed: {stats['documents_processed']}/{len(documents)}")
    print(f"Chunks created: {stats['chunks_created']}")
    print(f"Triplets extracted: {stats['triplets_extracted']}")
    print(f"Errors: {stats['errors']}")

    # Database statistics
    print("\n" + "="*70)
    print("Database Statistics")
    print("="*70)
    print(f"MySQL Documents: {mysql.get_document_count()}")
    print(f"MySQL Chunks: {mysql.get_chunk_count()}")
    print(f"ChromaDB Vectors: {chroma.get_count()}")
    print(f"BM25 Documents: {bm25.get_count()}")

    graph_stats = neo4j.get_statistics()
    print(f"Neo4j Nodes: {graph_stats.get('node_count', 0)}")
    print(f"Neo4j Relationships: {graph_stats.get('relationship_count', 0)}")

    # Cleanup
    print("\n" + "="*70)
    print("Saving BM25 index...")
    bm25.save_index()
    mysql.close()
    neo4j.close()

    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    if stats['errors'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
