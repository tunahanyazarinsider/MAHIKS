"""
Retrieval Agent for MAHIKS-TR
Responsible for hybrid retrieval from both vector database and knowledge graph.
Uses a two-stage chunking strategy: large chunks for recall, sub-chunks for precision.
"""
import spacy
from typing import List, Dict


class RetrievalAgent:
    """Agent for hybrid information retrieval"""

    # Sub-chunk settings for fine-grained reranking
    SUB_CHUNK_WORDS = 120
    SUB_CHUNK_OVERLAP = 30
    TOP_SUB_CHUNKS = 10
    CE_SCORE_THRESHOLD = 0.1  # Minimum reranker score to include in context

    def __init__(self, chroma_handler, neo4j_handler, mysql_handler, bm25_handler=None):
        self.chroma = chroma_handler
        self.neo4j = neo4j_handler
        self.mysql = mysql_handler
        # If the vector handler is hybrid (e.g. Qdrant with built-in BM25),
        # ignore any externally provided bm25_handler — fusion is done in-store.
        self.vector_is_hybrid = bool(getattr(chroma_handler, "is_hybrid", False))
        self.bm25 = None if self.vector_is_hybrid else bm25_handler

        # Load spaCy for entity extraction
        try:
            self.nlp = spacy.load("tr_core_news_lg")
        except OSError:
            print("⚠ Turkish spaCy model not loaded, entity extraction may be limited")
            self.nlp = None

        # Load BGE-reranker-v2-m3 for reranking (consistent with BGE-M3 embeddings)
        self.cross_encoder = None
        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
            print("✓ mmarco-mMiniLMv2 cross-encoder loaded for reranking")
        except ImportError:
            print("⚠ Install sentence-transformers: pip install sentence-transformers")
        except Exception as e:
            print(f"⚠ Cross-encoder not loaded: {e}")

        print("✓ Retrieval agent initialized")

    def extract_query_entities(self, query: str) -> List[str]:
        if not self.nlp:
            words = query.split()
            return [w for w in words if w[0].isupper() and len(w) > 2]

        doc = self.nlp(query)
        entities = []
        for ent in doc.ents:
            entities.append(ent.text)
        for chunk in doc.noun_chunks:
            if chunk.text not in entities:
                entities.append(chunk.text)
        return entities

    def vector_search(self, query: str, top_k: int = 5) -> List[Dict]:
        print(f"    Vector search for: '{query[:50]}...'")
        results_with_scores = self.chroma.query_with_scores(query, n_results=top_k)
        if not results_with_scores:
            print("      No vector results found")
            return []

        chunk_ids = [r['chunk_id'] for r in results_with_scores]
        chunks = self.mysql.get_chunks_by_ids(chunk_ids)

        for chunk in chunks:
            score_info = next(
                (r for r in results_with_scores if r['chunk_id'] == chunk['id']),
                None
            )
            if score_info:
                chunk['similarity'] = score_info['similarity']
                chunk['distance'] = score_info['distance']

        print(f"      ✓ Found {len(chunks)} relevant chunks")
        return chunks

    def graph_search(self, query: str) -> List[Dict]:
        print(f"    Graph search for query entities...")
        entities = self.extract_query_entities(query)
        if not entities:
            print("      No entities found in query")
            return []

        print(f"      Entities: {entities}")
        all_facts = []

        for entity in entities:
            related = self.neo4j.query_related_entities(entity, max_depth=2, limit=10)
            for rel in related:
                all_facts.append({
                    'source_entity': entity,
                    'target_entity': rel['entity'],
                    'relationship': rel['relationship'],
                    'labels': rel.get('labels', [])
                })

            if len(entities) > 1:
                for other_entity in entities:
                    if other_entity != entity:
                        path = self.neo4j.find_path(entity, other_entity, max_length=3)
                        if path:
                            all_facts.append({
                                'type': 'path',
                                'from': entity,
                                'to': other_entity,
                                'path': path
                            })

        print(f"      ✓ Found {len(all_facts)} graph facts")
        return all_facts

    def bm25_search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self.bm25:
            print("      BM25 not available")
            return []

        print(f"    BM25 search for: '{query[:50]}...'")
        results_with_scores = self.bm25.search(query, top_k)
        if not results_with_scores:
            print("      No BM25 results found")
            return []

        chunk_ids = [r[0] for r in results_with_scores]
        chunks = self.mysql.get_chunks_by_ids(chunk_ids)

        for chunk in chunks:
            score_info = next(
                (r for r in results_with_scores if r[0] == chunk['id']),
                None
            )
            if score_info:
                chunk['bm25_score'] = score_info[1]

        print(f"      ✓ Found {len(chunks)} relevant chunks")
        return chunks

    def fuse_results(self, vector_results: List[Dict], bm25_results: List[Dict], k: int = 60) -> List[Dict]:
        chunk_map = {}

        for rank, chunk in enumerate(vector_results, 1):
            chunk_id = chunk['id']
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk.copy()
                chunk_map[chunk_id]['rrf_score'] = 0
            chunk_map[chunk_id]['rrf_score'] += 1 / (k + rank)
            chunk_map[chunk_id]['vector_rank'] = rank

        for rank, chunk in enumerate(bm25_results, 1):
            chunk_id = chunk['id']
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk.copy()
                chunk_map[chunk_id]['rrf_score'] = 0
            chunk_map[chunk_id]['rrf_score'] += 1 / (k + rank)
            chunk_map[chunk_id]['bm25_rank'] = rank

        fused_results = sorted(
            chunk_map.values(),
            key=lambda x: x['rrf_score'],
            reverse=True
        )
        return fused_results

    def _split_into_sub_chunks(self, text: str, source_name: str,
                                chunk_id: int, similarity: float) -> List[Dict]:
        """
        Split a large chunk into smaller overlapping sub-chunks.

        Args:
            text: Full chunk text
            source_name: Source document name
            chunk_id: Parent chunk ID
            similarity: Original similarity score

        Returns:
            List of sub-chunk dicts with text and metadata
        """
        words = text.split()
        if len(words) <= self.SUB_CHUNK_WORDS:
            return [{
                'chunk_text': text,
                'source_name': source_name,
                'parent_chunk_id': chunk_id,
                'similarity': similarity,
            }]

        sub_chunks = []
        step = self.SUB_CHUNK_WORDS - self.SUB_CHUNK_OVERLAP
        for i in range(0, len(words), step):
            sub_text = ' '.join(words[i:i + self.SUB_CHUNK_WORDS])
            if len(sub_text.split()) < 20:  # skip tiny tail fragments
                break
            sub_chunks.append({
                'chunk_text': sub_text,
                'source_name': source_name,
                'parent_chunk_id': chunk_id,
                'similarity': similarity,
            })

        return sub_chunks

    def rerank_sub_chunks(self, chunks: List[Dict], query: str) -> List[Dict]:
        """
        Split chunks into sub-chunks and rerank with BGE-reranker-v2-m3.

        1. Take top 10 chunks from RRF fusion
        2. Split each into ~120 word overlapping sub-chunks
        3. Rerank all sub-chunks with cross-encoder
        4. Return top 10 sub-chunks

        Args:
            chunks: Fused chunks from RRF
            query: User query

        Returns:
            Top sub-chunks reranked by relevance
        """
        if not self.cross_encoder or not chunks:
            return chunks[:self.TOP_SUB_CHUNKS]

        # Take top 10 chunks for sub-chunking
        top_chunks = chunks[:10]

        # Split into sub-chunks
        all_sub_chunks = []
        for chunk in top_chunks:
            sub_chunks = self._split_into_sub_chunks(
                text=chunk.get('chunk_text', ''),
                source_name=chunk.get('source_name', 'Bilinmeyen'),
                chunk_id=chunk.get('id', 0),
                similarity=chunk.get('similarity', 0),
            )
            all_sub_chunks.extend(sub_chunks)

        print(f"    Split {len(top_chunks)} chunks → {len(all_sub_chunks)} sub-chunks ({self.SUB_CHUNK_WORDS} words each)")

        if not all_sub_chunks:
            return chunks[:self.TOP_SUB_CHUNKS]

        # Rerank sub-chunks with BGE-reranker-v2-m3
        texts = [sc['chunk_text'] for sc in all_sub_chunks]
        pairs = [[query, text] for text in texts]
        scores = self.cross_encoder.predict(pairs)

        for i, sc in enumerate(all_sub_chunks):
            sc['ce_score'] = float(scores[i])

        # Sort by reranker score, filter by threshold, take top N
        reranked = sorted(all_sub_chunks, key=lambda x: x['ce_score'], reverse=True)
        filtered = [sc for sc in reranked if sc['ce_score'] >= self.CE_SCORE_THRESHOLD]
        top_results = filtered[:self.TOP_SUB_CHUNKS]

        dropped = len(reranked) - len(filtered)
        total_words = sum(len(sc['chunk_text'].split()) for sc in top_results)
        print(f"    ✓ Reranked to {len(top_results)} sub-chunks (~{total_words} words), {dropped} below threshold")

        return top_results

    def hybrid_retrieve(self, query: str, vector_top_k: int = 10, use_reranking: bool = True) -> Dict:
        """
        Hybrid retrieval with sub-chunk reranking:
        1. Vector search → 10 results
        2. BM25 search → 10 results
        3. RRF fusion → top 10
        4. Sub-chunk + rerank → top 10 small chunks (~1200 words total)
        5. Graph search → entity relationships
        """
        print(f"\n  Hybrid retrieval for: '{query}'")

        # 1. Vector search
        vector_results = self.vector_search(query, top_k=vector_top_k)

        # 2. BM25 search
        bm25_results = []
        if self.bm25:
            bm25_results = self.bm25_search(query, top_k=vector_top_k)

        # 3. RRF fusion
        if bm25_results:
            fused_results = self.fuse_results(vector_results, bm25_results)
            print(f"    ✓ Fused {len(vector_results)} vector + {len(bm25_results)} BM25 results")
        else:
            fused_results = vector_results

        # 4. Sub-chunk and rerank
        if use_reranking and self.cross_encoder and fused_results:
            final_results = self.rerank_sub_chunks(fused_results, query)
        else:
            final_results = fused_results[:self.TOP_SUB_CHUNKS]

        # 5. Graph search
        graph_results = self.graph_search(query)

        result = {
            'query': query,
            'vector_context': final_results,
            'bm25_context': bm25_results,
            'graph_facts': graph_results,
            'total_sources': len(final_results) + len(graph_results)
        }

        print(f"  ✓ Retrieval complete: {len(final_results)} sub-chunks, "
              f"{len(graph_results)} graph facts\n")

        return result

    def get_context_window(self, chunk_id: int, window_size: int = 1) -> List[Dict]:
        chunks = self.mysql.get_chunks_by_ids([chunk_id])
        if not chunks:
            return []

        chunk = chunks[0]
        document_id = chunk['document_id']
        chunk_order = chunk['chunk_order']

        query = """
            SELECT * FROM chunks
            WHERE document_id = %s
            AND chunk_order BETWEEN %s AND %s
            ORDER BY chunk_order
        """
        self.mysql.cursor.execute(
            query,
            (document_id, chunk_order - window_size, chunk_order + window_size)
        )
        return self.mysql.cursor.fetchall()
