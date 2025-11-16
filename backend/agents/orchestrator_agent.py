"""
Orchestrator Agent for MAHIKS-TR
Coordinates the entire query processing pipeline
"""
from typing import Dict
import time


class QueryOrchestratorAgent:
    """Agent for orchestrating the query processing workflow"""

    def __init__(self, retrieval_agent, generation_agent):
        """
        Initialize the Orchestrator agent

        Args:
            retrieval_agent: Instance of RetrievalAgent
            generation_agent: Instance of GenerationAgent
        """
        self.retrieval_agent = retrieval_agent
        self.generation_agent = generation_agent
        print("✓ Query Orchestrator agent initialized")

    def process_query(self, user_query: str, include_citations: bool = True) -> Dict:
        """
        Orchestrate the complete query processing pipeline

        Args:
            user_query: User's question
            include_citations: Whether to include source citations

        Returns:
            Dictionary with answer and metadata
        """
        start_time = time.time()

        print(f"\n{'='*70}")
        print(f"Processing Query: {user_query}")
        print(f"{'='*70}")

        try:
            # Step 1: Retrieve relevant context (hybrid retrieval)
            print("\n[Step 1/2] Retrieving relevant context...")
            context = self.retrieval_agent.hybrid_retrieve(user_query)

            # Step 2: Generate answer using LLM
            print("\n[Step 2/2] Generating answer...")
            if include_citations:
                result = self.generation_agent.generate_with_citations(user_query, context)
                answer = result['answer']
                citations = result['citations']
            else:
                answer = self.generation_agent.generate_answer(user_query, context)
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
                            'relevance': chunk.get('similarity', 0)
                        }
                        for chunk in context.get('vector_context', [])[:3]
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
