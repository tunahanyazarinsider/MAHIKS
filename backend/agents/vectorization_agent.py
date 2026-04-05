"""
Vectorization Agent for MAHIKS-TR
Responsible for creating and storing vector embeddings
"""
from typing import List, Dict

from backend.agents.structure_aware_chunking_agent import Chunk


class VectorizationAgent:
    """Agent for vectorizing text chunks"""

    def __init__(self, chroma_handler, mysql_handler, bm25_handler=None):
        """
        Initialize the Vectorization agent

        Args:
            chroma_handler: Instance of ChromaDBHandler
            mysql_handler: Instance of MySQLHandler
            bm25_handler: Instance of BM25Handler (optional)
        """
        self.chroma = chroma_handler
        self.mysql = mysql_handler
        self.bm25 = bm25_handler
        print("✓ Vectorization agent initialized")

    def vectorize_chunks(self, chunks: List[Chunk], document_id: int) -> int:
        """
        Vectorize a list of chunks and store in ChromaDB

        Args:
            chunks: List of chunk objects with 'text' field
            document_id: ID of the parent document

        Returns:
            Number of chunks vectorized
        """
        if not chunks:
            print("    No chunks to vectorize")
            return 0

        print(f"    Vectorizing {len(chunks)} chunks...")

        chunk_ids = []
        texts = []
        metadatas = []

        # First, insert chunks into MySQL and collect IDs
        for idx, chunk in enumerate(chunks):
            chunk_id = self.mysql.insert_chunk(
                document_id=document_id,
                chunk_text=chunk.text,
                chunk_order=idx,
                metadata=chunk.metadata.to_dict() if chunk.metadata else None
            )
            chunk_ids.append(chunk_id)
            texts.append(chunk.text)

            # Prepare metadata for ChromaDB
            metadata = {
                'document_id': document_id,
                'chunk_order': idx,
                'context_header': getattr(chunk, 'context_header', '')
            }
            if chunk.metadata:
                metadata.update(chunk.metadata.to_dict())

            metadatas.append(metadata)

        # Now add to ChromaDB with MySQL chunk IDs
        self.chroma.add_chunks(chunk_ids, texts, metadatas)

        # Also add to BM25 index if available
        if self.bm25:
            self.bm25.add_chunks(chunk_ids, texts)

        print(f"      ✓ Vectorized {len(chunk_ids)} chunks")
        return len(chunk_ids)

    def vectorize_document(self, document_id: int) -> int:
        """
        Vectorize all chunks of an existing document from MySQL

        Args:
            document_id: Document ID in MySQL

        Returns:
            Number of chunks vectorized
        """
        print(f"    Vectorizing document ID: {document_id}")

        # Get chunks from MySQL
        chunks = self.mysql.get_all_chunks_for_document(document_id)

        if not chunks:
            print("      No chunks found for this document")
            return 0

        chunk_ids = [chunk['id'] for chunk in chunks]
        texts = [chunk['chunk_text'] for chunk in chunks]

        # Prepare metadata
        metadatas = []
        for chunk in chunks:
            metadata = {
                'document_id': document_id,
                'chunk_order': chunk['chunk_order']
            }
            if chunk.get('metadata_json'):
                import json
                try:
                    extra_metadata = json.loads(chunk['metadata_json'])
                    metadata.update(extra_metadata)
                except:
                    pass
            metadatas.append(metadata)

        # Add to ChromaDB
        self.chroma.add_chunks(chunk_ids, texts, metadatas)

        # Also add to BM25 index if available
        if self.bm25:
            self.bm25.add_chunks(chunk_ids, texts)

        print(f"      ✓ Vectorized {len(chunk_ids)} chunks")
        return len(chunk_ids)

    def update_vectors(self, chunk_ids: List[int]) -> int:
        """
        Update vectors for specific chunks (re-vectorize)

        Args:
            chunk_ids: List of chunk IDs to re-vectorize

        Returns:
            Number of chunks updated
        """
        if not chunk_ids:
            return 0

        print(f"    Updating vectors for {len(chunk_ids)} chunks...")

        # Get chunks from MySQL
        chunks = self.mysql.get_chunks_by_ids(chunk_ids)

        if not chunks:
            print("      No chunks found")
            return 0

        # Delete old vectors
        self.chroma.delete_chunks(chunk_ids)

        # Re-add with new vectors
        texts = [chunk['chunk_text'] for chunk in chunks]
        metadatas = []

        for chunk in chunks:
            metadata = {
                'document_id': chunk['document_id'],
                'chunk_order': chunk['chunk_order']
            }
            metadatas.append(metadata)

        self.chroma.add_chunks(chunk_ids, texts, metadatas)

        print(f"      ✓ Updated {len(chunk_ids)} vectors")
        return len(chunk_ids)

    def get_vectorization_stats(self) -> Dict:
        """
        Get statistics about vectorization

        Returns:
            Dictionary with stats
        """
        mysql_chunks = self.mysql.get_chunk_count()
        chroma_vectors = self.chroma.get_count()
        bm25_docs = self.bm25.get_count() if self.bm25 else 0

        return {
            'mysql_chunks': mysql_chunks,
            'chroma_vectors': chroma_vectors,
            'bm25_documents': bm25_docs,
            'in_sync': mysql_chunks == chroma_vectors == bm25_docs if self.bm25 else mysql_chunks == chroma_vectors
        }
