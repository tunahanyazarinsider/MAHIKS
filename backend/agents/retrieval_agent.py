"""
Retrieval Agent for MAHIKS-TR
Responsible for hybrid retrieval from both vector database and knowledge graph.
Uses a two-stage chunking strategy: large chunks for recall, sub-chunks for precision.
"""
import json
import os
import spacy
from typing import List, Dict


class RetrievalAgent:
    """Agent for hybrid information retrieval"""

    # Sub-chunk settings for fine-grained reranking
    SUB_CHUNK_WORDS = 120
    SUB_CHUNK_OVERLAP = 30
    TOP_SUB_CHUNKS = 10
    # Minimum reranker score to include in context.
    # mmarco-mMiniLMv2 emits negative scores for Turkish; default loosened to -10.
    CE_SCORE_THRESHOLD = float(os.getenv("CE_SCORE_THRESHOLD", "-10.0"))
    # Cap on graph facts returned by graph_search — keeps prompt and KG-path UI tight.
    MAX_GRAPH_FACTS = int(os.getenv("MAX_GRAPH_FACTS", "5"))

    def __init__(self, vector_handler, neo4j_handler, mysql_handler):
        # Qdrant hybrid handler: dense + sparse_bm25 with server-side RRF fusion.
        self.vector = vector_handler
        self.neo4j = neo4j_handler
        self.mysql = mysql_handler

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
        results_with_scores = self.vector.query_with_scores(query, n_results=top_k)
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

            if chunk.get('metadata_json'):
                try:
                    meta = json.loads(chunk['metadata_json'])
                    chunk.setdefault('section_number', meta.get('section_number', ''))
                    chunk.setdefault('section_title', meta.get('section_title', ''))
                except (json.JSONDecodeError, TypeError):
                    pass

        print(f"      ✓ Found {len(chunks)} relevant chunks")
        return chunks

    def graph_search(self, query: str) -> List[Dict]:
        """
        Return structured facts the frontend can render as pill chains.

        Two shapes:
          • {'type': 'triplet', 'source', 'rel', 'target', 'labels'}
          • {'type': 'path',    'nodes': [...], 'rels': [...]}

        Triplets are deduplicated and the whole list is capped so the LLM
        prompt and the UI both stay readable.
        """
        print(f"    Graph search for query entities...")
        entities = self.extract_query_entities(query)
        if not entities:
            print("      No entities found in query")
            return []

        print(f"      Entities: {entities}")
        triplets: List[Dict] = []
        seen_triplets = set()  # (source, rel, target) lowercase dedup keys
        paths: List[Dict] = []

        for entity in entities:
            related = self.neo4j.query_related_entities(entity, max_depth=2, limit=10)
            for rel in related:
                key = (entity.lower(), rel['relationship'], (rel['entity'] or '').lower())
                if key in seen_triplets:
                    continue
                seen_triplets.add(key)
                triplets.append({
                    'type': 'triplet',
                    'source': entity,
                    'rel': rel['relationship'],
                    'target': rel['entity'],
                    'labels': rel.get('labels', []),
                })

            if len(entities) > 1:
                for other_entity in entities:
                    if other_entity != entity:
                        p = self.neo4j.find_path(entity, other_entity, max_length=3)
                        if p and p.get('nodes'):
                            paths.append({
                                'type': 'path',
                                'nodes': p['nodes'],
                                'rels': p.get('relationships', []),
                            })

        # Paths first (multi-hop reasoning is more interesting to show),
        # then triplets. Capped overall — keeps the prompt tight and the
        # KG-path UI from sprawling.
        all_facts = (paths + triplets)[:self.MAX_GRAPH_FACTS]
        print(f"      ✓ Found {len(triplets)} triplets, {len(paths)} paths "
              f"→ returning {len(all_facts)}")
        return all_facts

    def _split_into_sub_chunks(self, text: str, source_name: str,
                                chunk_id: int, similarity: float,
                                section_number: str = '', section_title: str = '') -> List[Dict]:
        """
        Split a large chunk into smaller overlapping sub-chunks.

        Args:
            text: Full chunk text
            source_name: Source document name
            chunk_id: Parent chunk ID
            similarity: Original similarity score
            section_number: Section identifier from chunk metadata
            section_title: Section title from chunk metadata

        Returns:
            List of sub-chunk dicts with text and metadata
        """
        words = text.split()
        if len(words) <= self.SUB_CHUNK_WORDS:
            return [{
                'chunk_text': text,
                'source_name': source_name,
                'section_number': section_number,
                'section_title': section_title,
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
                'section_number': section_number,
                'section_title': section_title,
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
                section_number=chunk.get('section_number', ''),
                section_title=chunk.get('section_title', ''),
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
        1. Vector search → top_k results (Qdrant fuses dense + sparse_bm25 via RRF server-side)
        2. Sub-chunk + rerank → top sub-chunks (~1200 words total)
        3. Graph search → entity relationships
        """
        print(f"\n  Hybrid retrieval for: '{query}'")

        # 1. Vector search (already RRF-fused inside Qdrant)
        fused_results = self.vector_search(query, top_k=vector_top_k)

        # 4. Sub-chunk and rerank
        if use_reranking and self.cross_encoder and fused_results:
            final_results = self.rerank_sub_chunks(fused_results, query)
        else:
            final_results = fused_results[:self.TOP_SUB_CHUNKS]

        # 5. Graph search
        graph_results = self.graph_search(query)

        # Confidence summary — used by the orchestrator to decide whether
        # to hedge the LLM's answer when retrieval support is weak.
        ce_scores = [sc.get('ce_score') for sc in final_results if sc.get('ce_score') is not None]
        confidence = {
            'max_ce': max(ce_scores) if ce_scores else None,
            'mean_ce': (sum(ce_scores) / len(ce_scores)) if ce_scores else None,
            'passed_chunks': len(final_results),
        }

        result = {
            'query': query,
            'vector_context': final_results,
            'graph_facts': graph_results,
            'total_sources': len(final_results) + len(graph_results),
            'confidence': confidence,
        }

        print(f"  ✓ Retrieval complete: {len(final_results)} sub-chunks, "
              f"{len(graph_results)} graph facts "
              f"(max_ce={confidence['max_ce']})\n")

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
