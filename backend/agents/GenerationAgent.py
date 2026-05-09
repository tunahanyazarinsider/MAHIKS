"""
Generation Agent for MAHIKS-TR (Refactored)
=============================================

Uses a BaseLLMClient for all LLM calls — works with any provider
(Ollama, OpenRouter, OpenAI, Gemini, Vertex) without code changes.

Drop-in replacement for both GenerationAgentOllama and CloudGenerationAgent.
"""
from typing import Dict, List, Optional

from backend.agents.client.BaseLLMClient import BaseLLMClient


class GenerationAgent:
    """Provider-agnostic answer generation agent."""

    def __init__(self, llm_client: BaseLLMClient):
        """
        Args:
            llm_client: Any BaseLLMClient instance (from factory or manual init)
        """
        self.llm : BaseLLMClient = llm_client
        self.model : str = llm_client.model
        print(f"✓ GenerationAgent initialized (provider={llm_client.__class__.__name__}, model={self.model})")

    # ------------------------------------------------------------------
    # Context formatting
    # ------------------------------------------------------------------
    def format_vector_context(self, chunks: List[Dict], max_chunks: int = 10) -> str:
        """
        Format vector search results into context string

        Args:
            chunks: List of chunk dictionaries
            max_chunks: Maximum number of chunks to include

        Returns:
            Formatted context string
        """
        if not chunks:
            return "İlgili belge parçası bulunamadı."
        
        parts = []
        for i, chunk in enumerate(chunks[:max_chunks], 1):
            source = chunk.get('source_name', 'Bilinmeyen Kaynak')
            text = chunk['chunk_text']
            similarity = chunk.get('similarity', 0)
            parts.append(f"**Kaynak {i}** ({source}, Benzerlik: {similarity:.2%}):\n{text}\n")
        return "\n".join(parts)

    def format_graph_context(self, facts: List[Dict], max_facts: int = 10) -> str:
        """
        Format knowledge graph results into context string

        Args:
            facts: List of graph fact dictionaries
            max_facts: Maximum number of facts to include

        Returns:
            Formatted facts string
        """
        if not facts:
            return "İlişkili bilgi bulunamadı."
        
        parts = []
        for fact in facts[:max_facts]:
            if fact.get('type') == 'path':
                parts.append(f"• {fact['from']} ile {fact['to']} arasında bağlantı bulundu")
            else:
                s = fact.get('source_entity', '')
                t = fact.get('target_entity', '')
                r = fact.get('relationship', '')
                parts.append(f"• {s} → [{r}] → {t}")
        return "\n".join(parts)

    def _build_history_messages(self, messages: List[Dict]) -> List[Dict]:
    
        if not messages:
            return []
        history = []
        for msg in messages:
            role = "user" if msg.get('sender') == 'user' else "assistant"
            content = msg.get('content', '')
            if len(content) > 1000:
                content = content[:1000] + "..."
            history.append({"role": role, "content": content})
        return history

    # ------------------------------------------------------------------
    # Message building
    # ------------------------------------------------------------------
    def build_messages(self, query: str, context: Dict,
                       conversation_history: List[Dict] = None) -> List[Dict]:
        """
        Build the complete prompt for the LLM

        Args:
            query: User's question
            context: Retrieved context (vector + graph)

        Returns:
            Complete prompt string
        """
        vector_context = self.format_vector_context(context.get('vector_context', []))
        graph_context = self.format_graph_context(context.get('graph_facts', []))

        system_content = f"""Sen Türk sağlık sigortası konusunda uzman bir asistansın. Aşağıdaki bilgileri kullanarak soruyu yanıtla.

KURALLAR:
- Sadece verilen kaynaklara dayanarak yanıt ver
- Sana verilen bilgileri kullanarak soruyu yanıtla, dışarıdan bilgi ekleme
- Bilgi yoksa "Bu konuda yeterli bilgim yok" de
- Konuşma geçmişindeki bağlamı dikkate al
- Kısa ve net yanıtla, gerekirse madde işaretleri kullan
- Kaynaklara atıfta bulun
- Yanıtını Markdown formatında ver (başlıklar, maddeler, kalın yazı)

## İlgili Belge Parçaları:
{vector_context}

## Bilgi Grafiğinden İlişkiler:
{graph_context}"""

        messages = [{"role": "system", "content": system_content}]
        if conversation_history:
            messages.extend(self._build_history_messages(conversation_history))
        messages.append({"role": "user", "content": query})
        return messages

    # ------------------------------------------------------------------
    # Public API (same interface as GenerationAgentOllama)
    # ------------------------------------------------------------------
    def generate_answer(self, query: str, context: Dict,
                        temperature: float = 0.3, max_tokens: int = 2000,
                        conversation_history: List[Dict] = None) -> str:
        """
        Generate answer using LLM

        Args:
            query: User's question
            context: Retrieved context
            temperature: Model temperature (0-1)
            max_tokens: Maximum response length

        Returns:
            Generated answer
        """
        print(f"    Generating answer with {self.model}...")
        messages = self.build_messages(query, context, conversation_history)

        try:
            answer = self.llm.chat(messages, temperature, max_tokens)
            print(f"      ✓ Answer generated ({len(answer)} chars)")
            return answer
        except Exception as e:
            print(f"      ✗ Error generating answer: {e}")
            return f"Üzgünüm, yanıt oluştururken bir hata oluştu: {str(e)}"

    def generate_with_citations(self, query: str, context: Dict,
                                conversation_history: List[Dict] = None) -> Dict:
        """
        Generate answer with source citations

        Args:
            query: User's question
            context: Retrieved context

        Returns:
            Dictionary with answer and citations
        """

        answer = self.generate_answer(query, context,
                                      conversation_history=conversation_history)
        citations = []
        for chunk in context.get('vector_context', [])[:3]:
            citations.append({
                'source': chunk.get('source_name', 'Bilinmeyen'),
                'text': chunk.get('chunk_text', ''),
                'type': chunk.get('document_type', 'PDF'),
                'similarity': chunk.get('similarity', 0),
                'ce_score': chunk.get('ce_score', 'N/A'),
            })
        return {
            'answer': answer,
            'citations': citations,
            'graph_facts_used': len(context.get('graph_facts', []))
        }

    def generate_streaming(self, messages: List[Dict], max_tokens: int = 2000):
        """
        Stream tokens — delegates to llm_client.chat_stream.
        Args:
            messages: Chat messages array
            max_tokens: Maximum number of tokens to generate

        Yields:
            Text chunks (individual tokens/words)
        """
        try:
            yield from self.llm.chat_stream(messages, max_tokens=max_tokens)
        except Exception as e:
            print(f"Error during streaming generation: {e}")
            raise

    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        Generate a summary of a text

        Args:
            text: Text to summarize
            max_length: Maximum summary length in words

        Returns:
            Summary
        """
        messages = [
            {"role": "system", "content": "Sen metinleri özetleyen bir asistansın."},
            {"role": "user", "content": f"Aşağıdaki metni {max_length} kelime ile özetle:\n\n{text}"},
        ]
        try:
            return self.llm.chat(messages, temperature=0.3, max_tokens=500)
        except Exception as e:
            print(f"Error generating summary: {e}")
            return text[:500] + "..."

    def chat_completion(self, messages: List[Dict],
                        temperature: float = 0.3,
                        max_tokens: int = 2000) -> str:
        """
        Chat completion interface using Ollama /api/chat.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Model temperature
            max_tokens: Maximum response length

        Returns:
            Generated response
        """
        return self.llm.chat(messages, temperature, max_tokens)