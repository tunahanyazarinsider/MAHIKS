"""
ChromaDB Handler for MAHIKS-TR
Manages vector embeddings for semantic search
"""
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import numpy as np


class ChromaDBHandler:
    """Handler for ChromaDB vector database operations"""

    def __init__(self, persist_directory: str = "./chroma_data",
                 collection_name: str = "medical_chunks",
                 embedding_model_name: str = "BAAI/bge-m3"):
        """
        Initialize ChromaDB client and embedding model

        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Name of the collection
            embedding_model_name: SentenceTransformer model name for embeddings
        """
        print(f"Initializing ChromaDB at {persist_directory}...")

        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False,
            allow_reset=True,
            is_persistent=True
        ))

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        # Use multilingual model for Turkish support
        print(f"Loading embedding model ({embedding_model_name})...")
        try:
            self.embedding_model = SentenceTransformer(embedding_model_name)
        except Exception as e:
            print(f"⚠ Warning: Failed to download model with SSL verification: {e}")
            print("  Attempting to load without SSL verification...")
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            self.embedding_model = SentenceTransformer(embedding_model_name)
        print("✓ ChromaDB initialized successfully")

    def add_chunks(self, chunk_ids: List[int], texts: List[str],
                   metadatas: Optional[List[Dict]] = None):
        """
        Add text chunks with embeddings to the vector database

        Args:
            chunk_ids: List of MySQL chunk IDs
            texts: List of text contents
            metadatas: Optional metadata for each chunk
        """
        if not chunk_ids or not texts:
            print("  No chunks to add")
            return

        if len(chunk_ids) != len(texts):
            raise ValueError("chunk_ids and texts must have the same length")

        try:
            print(f"  Encoding {len(texts)} chunks...")
            # Generate embeddings
            embeddings = self.embedding_model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True
            ).tolist()

            # Prepare metadata
            if metadatas is None:
                metadatas = [{"chunk_id": cid} for cid in chunk_ids]
            else:
                # Ensure chunk_id is in metadata
                for i, meta in enumerate(metadatas):
                    meta["chunk_id"] = chunk_ids[i]

            # Add to ChromaDB
            self.collection.add(
                ids=[str(cid) for cid in chunk_ids],
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )

            print(f"  ✓ Added {len(chunk_ids)} chunks to vector database")
        except Exception as e:
            print(f"✗ Error adding chunks to ChromaDB: {e}")
            raise

    def query(self, query_text: str, n_results: int = 5) -> List[int]:
        """
        Query the vector database for similar chunks

        Args:
            query_text: The search query
            n_results: Number of results to return

        Returns:
            List of chunk IDs (as integers) sorted by relevance
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(
                [query_text],
                convert_to_numpy=True
            ).tolist()

            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=['metadatas', 'distances']
            )

            # Extract chunk IDs from metadata
            if results['metadatas'] and len(results['metadatas'][0]) > 0:
                chunk_ids = [
                    int(meta['chunk_id'])
                    for meta in results['metadatas'][0]
                ]
                return chunk_ids
            else:
                return []

        except Exception as e:
            print(f"✗ Error querying ChromaDB: {e}")
            return []

    def query_with_scores(self, query_text: str,
                         n_results: int = 5) -> List[Dict]:
        """
        Query with similarity scores

        Args:
            query_text: The search query
            n_results: Number of results to return

        Returns:
            List of dictionaries with chunk_id and similarity score
        """
        try:
            query_embedding = self.embedding_model.encode(
                [query_text],
                convert_to_numpy=True
            ).tolist()

            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=['metadatas', 'distances']
            )

            if results['metadatas'] and len(results['metadatas'][0]) > 0:
                return [
                    {
                        'chunk_id': int(meta['chunk_id']),
                        'distance': dist,
                        'similarity': 1 - dist  # Convert distance to similarity
                    }
                    for meta, dist in zip(
                        results['metadatas'][0],
                        results['distances'][0]
                    )
                ]
            else:
                return []

        except Exception as e:
            print(f"✗ Error querying ChromaDB with scores: {e}")
            return []

    def delete_chunks(self, chunk_ids: List[int]):
        """
        Delete chunks from the vector database

        Args:
            chunk_ids: List of chunk IDs to delete
        """
        try:
            self.collection.delete(
                ids=[str(cid) for cid in chunk_ids]
            )
            print(f"  ✓ Deleted {len(chunk_ids)} chunks from vector database")
        except Exception as e:
            print(f"✗ Error deleting chunks: {e}")

    def reset_collection(self):
        """Reset the entire collection (delete all data)"""
        try:
            self.client.delete_collection(name=self.collection.name)
            self.collection = self.client.create_collection(
                name=self.collection.name,
                metadata={"hnsw:space": "cosine"}
            )
            print("✓ Collection reset successfully")
        except Exception as e:
            print(f"✗ Error resetting collection: {e}")

    def get_count(self) -> int:
        """Get the number of vectors in the collection"""
        return self.collection.count()

    def peek(self, limit: int = 10) -> Dict:
        """
        Peek at some items in the collection

        Args:
            limit: Number of items to peek

        Returns:
            Dictionary with sample items
        """
        return self.collection.peek(limit=limit)
