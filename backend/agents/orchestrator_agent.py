"""
Orchestrator Agent for MAHIKS-TR
Coordinates the entire query processing pipeline
"""
from typing import Dict, List, Optional
from backend.database.cache_handler import get_cache_handler
from backend.agents.query_preprocessor import QueryPreprocessor
from backend.config import Config
import time


class QueryOrchestratorAgent:
    """Agent for orchestrating the query processing workflow"""

    def __init__(self, retrieval_agent, generation_agent, mysql_handler=None):
        """
        Initialize the Orchestrator agent

        Args:
            retrieval_agent: Instance of RetrievalAgent
            generation_agent: Instance of GenerationAgent
            mysql_handler: Instance of MySQLHandler (for conversation history)
        """
        self.retrieval_agent = retrieval_agent
        self.generation_agent = generation_agent
        self.mysql = mysql_handler or getattr(retrieval_agent, 'mysql', None)
        self.cache = get_cache_handler()
        self.preprocessor = QueryPreprocessor()
        print("✓ Query Orchestrator agent initialized")

    def process_query(self, user_query: str, include_citations: bool = True,
                      conversation_id: int = None) -> Dict:
        """
        Orchestrate the complete query processing pipeline

        Args:
            user_query: User's question
            include_citations: Whether to include source citations
            conversation_id: Optional conversation ID for context-aware responses

        Returns:
            Dictionary with answer and metadata
        """
        start_time = time.time()

        # Preprocess the query (typo correction, normalization)
        user_query = self.preprocessor.preprocess(user_query)

        # Only use cache for standalone queries (no conversation context)
        use_cache = self.cache and not conversation_id
        if use_cache:
            cached_response = self.cache.get_query_cache(user_query)
            if cached_response:
                cached_response['metadata']['from_cache'] = True
                cached_response['metadata']['response_time_ms'] = int(
                    (time.time() - start_time) * 1000
                )
                return cached_response

        print(f"\n{'='*70}")
        print(f"Processing Query: {user_query}")
        print(f"{'='*70}")

        try:
            # Fetch conversation history if conversation_id provided
            conversation_history = []
            if conversation_id and self.mysql:
                conversation_history = self.mysql.get_recent_messages(
                    conversation_id, limit=Config.CONVERSATION_HISTORY_LIMIT
                )

            # Build enhanced query for retrieval using conversation context
            enhanced_query = self._build_enhanced_query(user_query, conversation_history)

            # Step 1: Retrieve relevant context (hybrid retrieval)
            print("\n[Step 1/2] Retrieving relevant context...")
            context = self.retrieval_agent.hybrid_retrieve(enhanced_query)

            # Step 2: Generate answer using LLM
            print("\n[Step 2/2] Generating answer...")
            if include_citations:
                result = self.generation_agent.generate_with_citations(
                    user_query, context, conversation_history=conversation_history
                )
                answer = result['answer']
                citations = result['citations']
            else:
                answer = self.generation_agent.generate_answer(
                    user_query, context, conversation_history=conversation_history
                )
                citations = []

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Prepare response
            response = {
                'query': user_query,
                'answer': answer,
                'citations': citations,
                'sources': {
                    'documents': [
                        {
                            'name': chunk.get('source_name', 'Unknown'),
                            'type': chunk.get('document_type', 'Unknown'),
                            'relevance': chunk.get('similarity', 0),
                            'text': chunk.get('chunk_text', ''),
                        }
                        for chunk in context.get('vector_context', [])[:10]
                    ],
                    'graph_facts': len(context.get('graph_facts', []))
                },
                'metadata': {
                    'response_time_ms': response_time_ms,
                    'chunks_retrieved': len(context.get('vector_context', [])),
                    'facts_retrieved': len(context.get('graph_facts', [])),
                    'model': self.generation_agent.model
                }
            }

            print(f"\n{'='*70}")
            print(f"✓ Query processed successfully in {response_time_ms}ms")
            print(f"{'='*70}\n")

            # Store in cache for standalone queries
            if use_cache:
                self.cache.set_query_cache(user_query, response, ttl=Config.CACHE_TTL)
                response['metadata']['from_cache'] = False

            return response

        except Exception as e:
            error_time_ms = int((time.time() - start_time) * 1000)

            print(f"\n{'='*70}")
            print(f"✗ Error processing query: {e}")
            print(f"{'='*70}\n")

            return {
                'query': user_query,
                'answer': f"Üzgünüm, sorunuzu işlerken bir hata oluştu: {str(e)}",
                'error': str(e),
                'citations': [],
                'sources': {'documents': [], 'graph_facts': 0},
                'metadata': {
                    'response_time_ms': error_time_ms,
                    'success': False
                }
            }

    def stream_process_query(self, user_query: str, include_citations: bool = True,
                             conversation_id: int = None):
        """
        Streaming version of process_query. Performs retrieval first,
        then streams LLM generation token-by-token via SSE events.

        Yields:
            Dict events: {"type": "metadata"|"chunk"|"citations"|"done"|"error", "data": ...}
        """
        start_time = time.time()

        # Preprocess the query
        user_query = self.preprocessor.preprocess(user_query)

        try:
            # Fetch conversation history
            conversation_history = []
            if conversation_id and self.mysql:
                conversation_history = self.mysql.get_recent_messages(
                    conversation_id, limit=Config.CONVERSATION_HISTORY_LIMIT
                )

            # Build enhanced query for retrieval
            enhanced_query = self._build_enhanced_query(user_query, conversation_history)

            # Step 1: Retrieve context (blocking — fast)
            print(f"\n[Stream] Retrieving context for: {user_query}")
            context = self.retrieval_agent.hybrid_retrieve(enhanced_query)

            retrieval_time_ms = int((time.time() - start_time) * 1000)

            # Yield metadata event (sources info)
            sources = [
                {
                    'name': chunk.get('source_name', 'Unknown'),
                    'type': chunk.get('document_type', 'Unknown'),
                    'relevance': chunk.get('similarity', 0),
                }
                for chunk in context.get('vector_context', [])[:10]
            ]
            yield {
                "type": "metadata",
                "data": {
                    "chunks_retrieved": len(context.get('vector_context', [])),
                    "facts_retrieved": len(context.get('graph_facts', [])),
                    "retrieval_time_ms": retrieval_time_ms,
                    "sources": sources,
                    "model": self.generation_agent.model
                }
            }

            # Step 2: Build messages and stream generation
            messages = self.generation_agent.build_messages(
                user_query, context, conversation_history
            )

            full_answer = ""
            for token in self.generation_agent.generate_streaming(messages):
                full_answer += token
                yield {"type": "chunk", "data": token}

            # Step 3: Yield citations
            if include_citations:
                citations = []
                for chunk in context.get('vector_context', [])[:3]:
                    citations.append({
                        'source': chunk.get('source_name', 'Bilinmeyen'),
                        'type': chunk.get('document_type', 'PDF'),
                        'similarity': chunk.get('similarity', 0),
                        'ce_score': chunk.get('ce_score', 'N/A'),
                    })
                yield {"type": "citations", "data": citations}

            # Step 4: Done event
            response_time_ms = int((time.time() - start_time) * 1000)
            print(f"[Stream] ✓ Completed in {response_time_ms}ms")

            yield {
                "type": "done",
                "data": {
                    "response_time_ms": response_time_ms,
                    "answer": full_answer,
                }
            }

        except Exception as e:
            error_time_ms = int((time.time() - start_time) * 1000)
            print(f"[Stream] ✗ Error: {e}")
            yield {
                "type": "error",
                "data": {
                    "message": f"Üzgünüm, bir hata oluştu: {str(e)}",
                    "response_time_ms": error_time_ms
                }
            }

    def _build_enhanced_query(self, user_query: str,
                              conversation_history: List[Dict]) -> str:
        """
        Enhance the search query with conversation context.
        Extracts key terms from recent user messages to improve retrieval
        for follow-up questions like "explain more" or "bu ne demek".
        """
        if not conversation_history:
            return user_query

        # Extract key terms from the last 2-3 user messages
        recent_user_msgs = [
            m['content'] for m in conversation_history
            if m.get('sender') == 'user'
        ][-3:]

        query_words_lower = set(user_query.lower().split())
        context_terms = set()

        for msg in recent_user_msgs:
            words = msg.split()
            for word in words:
                if len(word) > 3 and word.lower() not in query_words_lower:
                    context_terms.add(word)

        if context_terms:
            enhancement = " ".join(list(context_terms)[:3])
            return f"{user_query} {enhancement}"

        return user_query

    def process_batch_queries(self, queries: list) -> list:
        """
        Process multiple queries in batch

        Args:
            queries: List of query strings

        Returns:
            List of response dictionaries
        """
        results = []

        print(f"\nProcessing batch of {len(queries)} queries...")

        for i, query in enumerate(queries, 1):
            print(f"\n--- Query {i}/{len(queries)} ---")
            result = self.process_query(query)
            results.append(result)

        print(f"\n✓ Batch processing complete: {len(results)} queries processed")

        return results

    def get_pipeline_status(self) -> Dict:
        """
        Get status of all pipeline components

        Returns:
            Status dictionary
        """
        try:
            # Get vectorization stats
            vec_stats = self.retrieval_agent.mysql.get_chunk_count()

            # Get graph stats
            graph_stats = self.retrieval_agent.neo4j.get_statistics()

            # Get document count
            doc_count = self.retrieval_agent.mysql.get_document_count()

            return {
                'status': 'operational',
                'documents': doc_count,
                'chunks': vec_stats,
                'vectors': self.retrieval_agent.chroma.get_count(),
                'graph': {
                    'nodes': graph_stats.get('node_count', 0),
                    'relationships': graph_stats.get('relationship_count', 0)
                },
                'components': {
                    'retrieval_agent': 'ready',
                    'generation_agent': 'ready',
                    'databases': 'connected'
                }
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'components': {
                    'retrieval_agent': 'unknown',
                    'generation_agent': 'unknown',
                    'databases': 'unknown'
                }
            }
