"""
BM25 Handler for MAHIKS-TR
Manages BM25 lexical search for keyword-based retrieval
"""
import pickle
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
from TurkishStemmer import TurkishStemmer


class BM25Handler:
    """Handler for BM25 lexical search operations"""

    def __init__(self, persist_directory: str = "./bm25_data",
                 k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 handler

        Args:
            persist_directory: Directory to persist BM25 index
            k1: BM25 term frequency saturation parameter (default: 1.5)
            b: BM25 length normalization parameter (default: 0.75)
        """
        print(f"Initializing BM25 handler at {persist_directory}...")
        
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.k1 = k1
        self.b = b
        
        # BM25 index and metadata
        self.bm25 = None
        self.chunk_ids = []  # Maps doc index -> chunk_id
        self.tokenized_corpus = []  # Stores tokenized documents

        self.stemmer = TurkishStemmer()
        
        # Try to load existing index
        self._load_index()
        
        print("✓ BM25 handler initialized successfully")

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing
        Uses simple but effective tokenization suitable for Turkish

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation but keep alphanumeric and Turkish characters
        # Preserve medical abbreviations and terms
        text = re.sub(r'[^\w\sçğıöşüÇĞİÖŞÜ]', ' ', text)
        
        # Split on whitespace and filter empty strings
        tokens = text.split()

        # Stem tokens
        stemmed_tokens = [self.stemmer.stem(token) for token in tokens]
        
        return stemmed_tokens

    def add_chunks(self, chunk_ids: List[int], texts: List[str]) -> None:
        """
        Add text chunks to BM25 index

        Args:
            chunk_ids: List of MySQL chunk IDs
            texts: List of text contents
        """

        new_ids = []
        new_texts = []
        
        existing_ids = set(self.chunk_ids) 
        
        for chunk_id, text in zip(chunk_ids, texts):
            if chunk_id not in existing_ids:
                new_ids.append(chunk_id)
                new_texts.append(text)
        
        
        if not new_ids or not new_texts:
            print("  No chunks to add to BM25")
            return

        try:
            print(f"  Tokenizing {len(new_texts)} chunks for BM25...")
            
            # Tokenize all texts
            tokenized_texts = [self._tokenize(text) for text in new_texts]
            
            # Add to existing corpus
            self.tokenized_corpus.extend(tokenized_texts)
            self.chunk_ids.extend(new_ids)
            
            # Rebuild BM25 index with entire corpus
            self.bm25 = BM25Okapi(self.tokenized_corpus, k1=self.k1, b=self.b)
            
            print(f"  ✓ Added {len(new_ids)} chunks to BM25 index")
            
        except Exception as e:
            print(f"✗ Error adding chunks to BM25: {e}")
            raise

    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        """
        Search BM25 index for relevant chunks

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of (chunk_id, score) tuples sorted by relevance
        """
        if self.bm25 is None or len(self.chunk_ids) == 0:
            print("  BM25 index is empty")
            return []

        try:
            # Tokenize query
            tokenized_query = self._tokenize(query)
            
            if not tokenized_query:
                return []
            
            # Get BM25 scores for all documents
            scores = self.bm25.get_scores(tokenized_query)
            
            # Get top-k indices
            top_indices = np.argsort(scores)[::-1][:top_k]
            
            # Filter out zero scores and map to chunk_ids
            results = [
                (self.chunk_ids[idx], float(scores[idx]))
                for idx in top_indices
                if scores[idx] > 0
            ]

            return results
            
        except Exception as e:
            print(f"✗ Error searching BM25: {e}")
            return []

    def get_top_k(self, query: str, top_k: int = 5) -> List[int]:
        """
        Get top-k chunk IDs for a query (convenience method)

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of chunk IDs sorted by relevance
        """
        results = self.search(query, top_k)
        return [chunk_id for chunk_id, _ in results]

    def save_index(self) -> None:
        """Save BM25 index to disk for persistence"""
        try:
            index_path = self.persist_dir / "bm25_index.pkl"
            
            index_data = {
                'chunk_ids': self.chunk_ids,
                'tokenized_corpus': self.tokenized_corpus,
                'k1': self.k1,
                'b': self.b
            }
            
            with open(index_path, 'wb') as f:
                pickle.dump(index_data, f)
            
            print(f"  ✓ BM25 index saved to {index_path}")
            
        except Exception as e:
            print(f"✗ Error saving BM25 index: {e}")

    def _load_index(self) -> bool:
        """
        Load BM25 index from disk

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            index_path = self.persist_dir / "bm25_index.pkl"
            
            if not index_path.exists():
                print("  No existing BM25 index found")
                return False
            
            with open(index_path, 'rb') as f:
                index_data = pickle.load(f)
            
            self.chunk_ids = index_data['chunk_ids']
            self.tokenized_corpus = index_data['tokenized_corpus']
            self.k1 = index_data.get('k1', self.k1)
            self.b = index_data.get('b', self.b)
            
            # Rebuild BM25 index
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus, k1=self.k1, b=self.b)
                print(f"  ✓ Loaded BM25 index with {len(self.chunk_ids)} documents")
            
            return True
            
        except Exception as e:
            print(f"  ⚠ Could not load BM25 index: {e}")
            return False

    def reset_index(self) -> None:
        """Reset the entire BM25 index (delete all data)"""
        try:
            self.bm25 = None
            self.chunk_ids = []
            self.tokenized_corpus = []
            
            # Delete persisted index
            index_path = self.persist_dir / "bm25_index.pkl"
            if index_path.exists():
                index_path.unlink()
            
            print("✓ BM25 index reset successfully")
            
        except Exception as e:
            print(f"✗ Error resetting BM25 index: {e}")

    def get_count(self) -> int:
        """Get the number of documents in the BM25 index"""
        return len(self.chunk_ids)

    def get_stats(self) -> Dict:
        """
        Get statistics about the BM25 index

        Returns:
            Dictionary with index statistics
        """
        return {
            'document_count': len(self.chunk_ids),
            'k1': self.k1,
            'b': self.b,
            'persist_directory': str(self.persist_dir),
            'index_exists': self.bm25 is not None
        }
