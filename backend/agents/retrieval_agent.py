"""
Retrieval Agent for MAHIKS-TR
Responsible for hybrid retrieval from both vector database and knowledge graph
"""
import spacy
from typing import List, Dict


class RetrievalAgent:
    """Agent for hybrid information retrieval"""

    def __init__(self, chroma_handler, neo4j_handler, mysql_handler, bm25_handler=None):
        """
        Initialize the Retrieval agent

        Args:
            chroma_handler: Instance of ChromaDBHandler
            neo4j_handler: Instance of Neo4jHandler
            mysql_handler: Instance of MySQLHandler
            bm25_handler: Instance of BM25Handler (optional)
        """
        self.chroma = chroma_handler
        self.neo4j = neo4j_handler
        self.mysql = mysql_handler
        self.bm25 = bm25_handler

        # Load spaCy for entity extraction from queries
        try:
            self.nlp = spacy.load("tr_core_news_lg")
        except OSError:
            print("⚠ Turkish spaCy model not loaded, entity extraction may be limited")
            self.nlp = None

        print("✓ Retrieval agent initialized")

    def extract_query_entities(self, query: str) -> List[str]:
        """
        Extract entities from user query

        Args:
            query: User's question

        Returns:
            List of entity names
        """
        if not self.nlp:
            # Fallback: extract capitalized words
            words = query.split()
            return [w for w in words if w[0].isupper() and len(w) > 2]

        doc = self.nlp(query)
        entities = []

        for ent in doc.ents:
            entities.append(ent.text)

        # Also add noun chunks as potential entities
        for chunk in doc.noun_chunks:
            if chunk.text not in entities:
                entities.append(chunk.text)

        return entities

    def vector_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Perform semantic search in vector database

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of chunks with similarity scores
        """
        print(f"    Vector search for: '{query[:50]}...'")

        # Get chunk IDs from ChromaDB
        results_with_scores = self.chroma.query_with_scores(query, n_results=top_k)

        if not results_with_scores:
            print("      No vector results found")
            return []

        # Get full chunk data from MySQL
        chunk_ids = [r['chunk_id'] for r in results_with_scores]
        chunks = self.mysql.get_chunks_by_ids(chunk_ids)

        # Add similarity scores
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
        """
        Search knowledge graph for related entities and facts

        Args:
            query: Search query

        Returns:
            List of graph facts and relationships
        """
        print(f"    Graph search for query entities...")

        # Extract entities from query
        entities = self.extract_query_entities(query)

        if not entities:
            print("      No entities found in query")
            return []

        print(f"      Entities: {entities}")

        all_facts = []

        # Query graph for each entity
        for entity in entities:
            # Get related entities
            related = self.neo4j.query_related_entities(entity, max_depth=2, limit=10)

            for rel in related:
                all_facts.append({
                    'source_entity': entity,
                    'target_entity': rel['entity'],
                    'relationship': rel['relationship'],
                    'labels': rel.get('labels', [])
                })

            # Also try to find paths between entities if multiple exist
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
        """
        Perform BM25 lexical search

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of chunks with BM25 scores
        """
        if not self.bm25:
            print("      BM25 not available")
            return []

        print(f"    BM25 search for: '{query[:50]}...'")

        # Get chunk IDs and scores from BM25
        results_with_scores = self.bm25.search(query, top_k)

        if not results_with_scores:
            print("      No BM25 results found")
            return []

        # Get full chunk data from MySQL
        chunk_ids = [r[0] for r in results_with_scores]
        chunks = self.mysql.get_chunks_by_ids(chunk_ids)

        # Add BM25 scores
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
        """
        Fuse vector and BM25 results using Reciprocal Rank Fusion (RRF)

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            k: RRF constant (default: 60)

        Returns:
            Fused and re-ranked results
        """
        # Create mapping of chunk_id to chunk data
        chunk_map = {}
        
        # Add vector results with their ranks
        for rank, chunk in enumerate(vector_results, 1):
            chunk_id = chunk['id']
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk.copy()
                chunk_map[chunk_id]['rrf_score'] = 0
            chunk_map[chunk_id]['rrf_score'] += 1 / (k + rank)
            chunk_map[chunk_id]['vector_rank'] = rank

        # Add BM25 results with their ranks
        for rank, chunk in enumerate(bm25_results, 1):
            chunk_id = chunk['id']
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk.copy()
                chunk_map[chunk_id]['rrf_score'] = 0
            chunk_map[chunk_id]['rrf_score'] += 1 / (k + rank)
            chunk_map[chunk_id]['bm25_rank'] = rank

        # Sort by RRF score
        fused_results = sorted(
            chunk_map.values(),
            key=lambda x: x['rrf_score'],
            reverse=True
        )

        return fused_results

    def hybrid_retrieve(self, query: str, vector_top_k: int = 5) -> Dict:
        """
        Perform triple-hybrid retrieval: combine vector, BM25, and graph search

        Args:
            query: User query
            vector_top_k: Number of vector results

        Returns:
            Dictionary with vector, BM25, graph results, and fused context
        """
        print(f"\n  Hybrid retrieval for: '{query}'")

        # 1. Vector search
        vector_results = self.vector_search(query, top_k=vector_top_k)

        # 2. BM25 search (if available)
        bm25_results = []
        if self.bm25:
            bm25_results = self.bm25_search(query, top_k=vector_top_k)

        # 3. Fuse vector and BM25 results
        if bm25_results:
            fused_context = self.fuse_results(vector_results, bm25_results)
            print(f"    ✓ Fused {len(vector_results)} vector + {len(bm25_results)} BM25 results")
        else:
            fused_context = vector_results

        # 4. Graph search
        graph_results = self.graph_search(query)

        result = {
            'query': query,
            'vector_context': vector_results,
            'bm25_context': bm25_results,
            'graph_facts': graph_results,
            'fused_context': fused_context,  # Combined vector + BM25
            'total_sources': len(vector_results) + len(bm25_results) + len(graph_results)
        }

        print(f"  ✓ Retrieval complete: {len(vector_results)} vector, "
              f"{len(bm25_results)} BM25, {len(graph_results)} graph facts\n")

        return result

    def rerank_results(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Re-rank results based on additional criteria
        (Could be enhanced with a re-ranking model)

        Args:
            results: List of retrieved chunks
            query: Original query

        Returns:
            Re-ranked results
        """
        # Simple re-ranking based on similarity score
        # Can be enhanced with cross-encoder models
        return sorted(results, key=lambda x: x.get('similarity', 0), reverse=True)

    def get_context_window(self, chunk_id: int, window_size: int = 1) -> List[Dict]:
        """
        Get surrounding chunks for context

        Args:
            chunk_id: Center chunk ID
            window_size: Number of chunks before and after

        Returns:
            List of chunks including context
        """
        # Get the chunk
        chunks = self.mysql.get_chunks_by_ids([chunk_id])
        if not chunks:
            return []

        chunk = chunks[0]
        document_id = chunk['document_id']
        chunk_order = chunk['chunk_order']

        # Get surrounding chunks
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
