"""
Qdrant Handler for MAHIKS-TR
Stores two named vectors per point: dense (BGE-M3) + sparse_bm25 (FastEmbed BM25).
Hybrid retrieval is performed inside Qdrant via Prefetch + RRF fusion.
"""
import os
import ssl

# SSL bypass for environments behind self-signed cert proxies.
# Applied once at module import; affects HuggingFace Hub + FastEmbed downloads.
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
ssl._create_default_https_context = ssl._create_unverified_context
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import requests
    _orig_request = requests.Session.request

    def _patched_request(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        return _orig_request(self, *args, **kwargs)
    requests.Session.request = _patched_request
except Exception:
    pass

from typing import List, Dict, Optional

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseVector,
    Modifier,
    PointStruct,
    Prefetch,
    FusionQuery,
    Fusion,
    NamedVector,
)


class QdrantHandler:
    """Hybrid (dense + sparse BM25) Qdrant vector store handler."""

    is_hybrid = True

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: Optional[str] = None,
        collection_name: str = "sut_documents",
        embedding_model_name: str = "BAAI/bge-m3",
        dense_vector_name: str = "dense",
        sparse_vector_name: str = "sparse_bm25",
        sparse_model_name: str = "Qdrant/bm25",
        sparse_language: str = "turkish",
        dense_dim: int = 1024,
    ):
        print(f"Initializing Qdrant at {url}...")
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
        self.dense_name = dense_vector_name
        self.sparse_name = sparse_vector_name
        self.dense_dim = dense_dim

        print(f"Loading dense embedding model ({embedding_model_name})...")
        try:
            self.embedding_model = SentenceTransformer(embedding_model_name)
        except Exception as e:
            print(f"⚠ SSL fallback for dense model: {e}")
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            self.embedding_model = SentenceTransformer(embedding_model_name)

        print(f"Loading sparse model ({sparse_model_name}, lang={sparse_language})...")
        from fastembed import SparseTextEmbedding
        self.sparse_model = SparseTextEmbedding(
            model_name=sparse_model_name,
            language=sparse_language,
        )

        self._ensure_collection()
        print("✓ Qdrant initialized successfully")

    # ------------------------------------------------------------------
    # Collection lifecycle
    # ------------------------------------------------------------------
    def _ensure_collection(self):
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection_name in existing:
            return
        print(f"Creating Qdrant collection '{self.collection_name}'...")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                self.dense_name: VectorParams(
                    size=self.dense_dim,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                self.sparse_name: SparseVectorParams(
                    modifier=Modifier.IDF,
                ),
            },
        )

    def reset_collection(self):
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as e:
            print(f"  (delete_collection: {e})")
        self._ensure_collection()
        print("✓ Collection reset successfully")

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------
    def _encode_dense(self, texts: List[str]) -> List[List[float]]:
        return self.embedding_model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).tolist()

    def _encode_sparse_docs(self, texts: List[str]) -> List[SparseVector]:
        out = []
        for emb in self.sparse_model.embed(texts):
            out.append(SparseVector(
                indices=emb.indices.tolist(),
                values=emb.values.tolist(),
            ))
        return out

    def _encode_sparse_query(self, text: str) -> SparseVector:
        emb = next(self.sparse_model.query_embed(text))
        return SparseVector(
            indices=emb.indices.tolist(),
            values=emb.values.tolist(),
        )

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------
    def add_chunks(
        self,
        chunk_ids: List[int],
        texts: List[str],
        metadatas: Optional[List[Dict]] = None,
    ):
        if not chunk_ids or not texts:
            print("  No chunks to add")
            return
        if len(chunk_ids) != len(texts):
            raise ValueError("chunk_ids and texts must have the same length")

        try:
            print(f"  Encoding {len(texts)} chunks (dense + sparse)...")
            dense_vecs = self._encode_dense(texts)
            sparse_vecs = self._encode_sparse_docs(texts)

            if metadatas is None:
                metadatas = [{"chunk_id": cid} for cid in chunk_ids]
            else:
                for i, meta in enumerate(metadatas):
                    meta["chunk_id"] = chunk_ids[i]
                    for k, v in list(meta.items()):
                        if v is None:
                            meta[k] = ""
                        elif not isinstance(v, (str, int, float, bool, list, dict)):
                            meta[k] = str(v)

            payloads = []
            for i, meta in enumerate(metadatas):
                p = dict(meta)
                p["chunk_text"] = texts[i]
                payloads.append(p)

            points = [
                PointStruct(
                    id=int(chunk_ids[i]),
                    vector={
                        self.dense_name: dense_vecs[i],
                        self.sparse_name: sparse_vecs[i],
                    },
                    payload=payloads[i],
                )
                for i in range(len(chunk_ids))
            ]

            self.client.upsert(collection_name=self.collection_name, points=points)
            print(f"  ✓ Added {len(chunk_ids)} chunks to Qdrant")
        except Exception as e:
            print(f"✗ Error adding chunks to Qdrant: {e}")
            raise

    def delete_chunks(self, chunk_ids: List[int]):
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[int(cid) for cid in chunk_ids],
                ),
            )
            print(f"  ✓ Deleted {len(chunk_ids)} chunks from Qdrant")
        except Exception as e:
            print(f"✗ Error deleting chunks: {e}")

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------
    def query(self, query_text: str, n_results: int = 5) -> List[int]:
        try:
            results = self._hybrid_query(query_text, n_results)
            return [int(p.payload.get("chunk_id", p.id)) for p in results]
        except Exception as e:
            print(f"✗ Error querying Qdrant: {e}")
            return []

    def query_with_scores(self, query_text: str, n_results: int = 5) -> List[Dict]:
        try:
            results = self._hybrid_query(query_text, n_results)
            out = []
            for p in results:
                out.append({
                    "chunk_id": int(p.payload.get("chunk_id", p.id)),
                    "distance": 1.0 - float(p.score),
                    "similarity": float(p.score),
                })
            return out
        except Exception as e:
            print(f"✗ Error querying Qdrant with scores: {e}")
            return []

    def _hybrid_query(self, query_text: str, n_results: int):
        dense_vec = self._encode_dense([query_text])[0]
        sparse_vec = self._encode_sparse_query(query_text)

        prefetch = [
            Prefetch(
                query=dense_vec,
                using=self.dense_name,
                limit=max(n_results * 2, n_results),
            ),
            Prefetch(
                query=sparse_vec,
                using=self.sparse_name,
                limit=max(n_results * 2, n_results),
            ),
        ]

        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=prefetch,
            query=FusionQuery(fusion=Fusion.RRF),
            limit=n_results,
            with_payload=True,
        )
        return response.points

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def get_count(self) -> int:
        try:
            return self.client.count(
                collection_name=self.collection_name,
                exact=True,
            ).count
        except Exception as e:
            print(f"✗ count error: {e}")
            return 0

    def peek(self, limit: int = 10) -> Dict:
        try:
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            return {
                "ids": [p.id for p in points],
                "metadatas": [p.payload for p in points],
            }
        except Exception as e:
            print(f"✗ peek error: {e}")
            return {"ids": [], "metadatas": []}
