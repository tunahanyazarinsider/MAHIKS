"""
Generation Agent for MAHIKS-TR using Ollama
Responsible for generating answers using local LLM with retrieved context.
Uses Ollama's /api/chat endpoint for proper chat template handling.
"""
from typing import Dict, List, Optional
import requests
import json


class GenerationAgentOllama:
    """Agent for answer generation using Ollama (local LLM)"""

    def __init__(self,
                 base_url: str = "http://localhost:11434",
                 model: str = "qwen2.5:7b"):
        """
        Initialize the Generation agent with Ollama

        Args:
            base_url: Ollama API base URL
            model: Model to use
        """
        self.base_url = base_url.rstrip('/')
        self.model = model

        # Test connection
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                available_models = [m['name'] for m in response.json().get('models', [])]
                if self.model not in available_models:
                    print(f"⚠ Warning: Model '{self.model}' not found in Ollama.")
                    print(f"  Available models: {', '.join(available_models)}")
                    if available_models:
                        print(f"  Consider pulling the model: ollama pull {self.model}")
                print(f"✓ Generation agent initialized (Ollama, model={model})")
            else:
                print(f"⚠ Warning: Could not connect to Ollama at {self.base_url}")
        except Exception as e:
            print(f"⚠ Warning: Ollama connection test failed: {e}")
            print(f"  Make sure Ollama is running: ollama serve")

    def format_vector_context(self, chunks: List[Dict], max_chunks: int = 10) -> str:
        """Format vector search results into context string"""
        if not chunks:
            return "İlgili belge parçası bulunamadı."

        context_parts = []
        for i, chunk in enumerate(chunks[:max_chunks], 1):
            source = chunk.get('source_name', 'Bilinmeyen Kaynak')
            text = chunk['chunk_text']
            similarity = chunk.get('similarity', 0)
            context_parts.append(
                f"**Kaynak {i}** ({source}, Benzerlik: {similarity:.2%}):\n{text}\n"
            )
        return "\n".join(context_parts)

    def format_graph_context(self, facts: List[Dict], max_facts: int = 10) -> str:
        """Format knowledge graph results into context string"""
        if not facts:
            return "İlişkili bilgi bulunamadı."

        fact_parts = []
        for fact in facts[:max_facts]:
            if fact.get('type') == 'path':
                path_info = f"• {fact['from']} ile {fact['to']} arasında bağlantı bulundu"
                fact_parts.append(path_info)
            else:
                source = fact.get('source_entity', '')
                target = fact.get('target_entity', '')
                rel = fact.get('relationship', '')
                fact_parts.append(f"• {source} → [{rel}] → {target}")
        return "\n".join(fact_parts)

    def _build_history_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        Convert conversation history to Ollama chat message format.

        Args:
            messages: List of message dicts with 'sender' and 'content' keys

        Returns:
            List of {"role": "user"|"assistant", "content": ...} dicts
        """
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

    def build_messages(self, query: str, context: Dict,
                       conversation_history: List[Dict] = None) -> List[Dict]:
        """
        Build the chat messages array for Ollama /api/chat.

        Args:
            query: User's question
            context: Retrieved context (vector + graph)
            conversation_history: Optional list of previous messages

        Returns:
            List of message dicts for /api/chat
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

        # Add conversation history as prior turns
        if conversation_history:
            messages.extend(self._build_history_messages(conversation_history))

        messages.append({"role": "user", "content": query})
        return messages

    def generate_answer(self, query: str, context: Dict,
                       temperature: float = 0.3,
                       max_tokens: int = 2000,
                       conversation_history: List[Dict] = None) -> str:
        """
        Generate answer using Ollama /api/chat endpoint.

        Args:
            query: User's question
            context: Retrieved context
            temperature: Model temperature (0-1)
            max_tokens: Maximum response length
            conversation_history: Optional previous messages for context

        Returns:
            Generated answer
        """
        print(f"    Generating answer with Ollama ({self.model})...")

        messages = self.build_messages(query, context, conversation_history)

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                },
                timeout=180
            )

            if response.status_code == 200:
                result = response.json()
                answer = result.get('message', {}).get('content', '')
                print(f"      ✓ Answer generated ({len(answer)} chars)")
                return answer
            else:
                error_msg = f"Ollama API error: {response.status_code}"
                print(f"      ✗ {error_msg}")
                return f"Üzgünüm, yanıt oluştururken bir hata oluştu: {error_msg}"

        except requests.exceptions.Timeout:
            print(f"      ✗ Request timeout")
            return "Üzgünüm, yanıt oluşturma süresi çok uzun sürdü. Lütfen tekrar deneyin."
        except Exception as e:
            print(f"      ✗ Error generating answer: {e}")
            return f"Üzgünüm, yanıt oluştururken bir hata oluştu: {str(e)}"

    def generate_with_citations(self, query: str, context: Dict,
                                conversation_history: List[Dict] = None) -> Dict:
        """
        Generate answer with source citations.

        Args:
            query: User's question
            context: Retrieved context
            conversation_history: Optional previous messages for context

        Returns:
            Dictionary with answer and citations
        """
        answer = self.generate_answer(query, context,
                                      conversation_history=conversation_history)

        citations = []
        for chunk in context.get('vector_context', [])[:3]:
            citation = {
                'source': chunk.get('source_name', 'Bilinmeyen'),
                'text': chunk.get('chunk_text', ''),
                'type': chunk.get('document_type', 'PDF'),
                'similarity': chunk.get('similarity', 0),
                'ce_score': chunk.get('ce_score', 'N/A'),
            }
            citations.append(citation)

        return {
            'answer': answer,
            'citations': citations,
            'graph_facts_used': len(context.get('graph_facts', []))
        }

    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """Generate a summary of a text using /api/chat."""
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Sen metinleri özetleyen bir asistansın."},
                        {"role": "user", "content": f"Aşağıdaki metni {max_length} kelime ile özetle:\n\n{text}"}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', text[:500] + "...")
            else:
                print(f"Error generating summary: API returned {response.status_code}")
                return text[:500] + "..."

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
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                },
                timeout=180
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', '')
            else:
                raise Exception(f"API returned status {response.status_code}")

        except Exception as e:
            raise Exception(f"Chat completion failed: {str(e)}")

    def generate_streaming(self, messages: List[Dict], max_tokens: int = 2000):
        """
        Generate answer with streaming response using /api/chat.
        Each Ollama streaming line is JSON: {"message": {"content": "token"}, "done": false}

        Args:
            messages: Chat messages array
            max_tokens: Maximum number of tokens to generate

        Yields:
            Text chunks (individual tokens/words)
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": max_tokens,
                    }
                },
                stream=True,
                timeout=180
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            token = data.get('message', {}).get('content', '')
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
            else:
                raise Exception(f"Ollama API returned status {response.status_code}")

        except Exception as e:
            print(f"Error during streaming generation: {e}")
            raise
