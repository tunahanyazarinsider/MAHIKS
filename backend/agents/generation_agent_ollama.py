"""
Generation Agent for MAHIKS-TR using Ollama
Responsible for generating answers using local LLM with retrieved context
"""
from typing import Dict, List, Optional
import requests
import json


class GenerationAgentOllama:
    """Agent for answer generation using Ollama (local LLM)"""

    def __init__(self,
                 base_url: str = "http://localhost:11434",
                 model: str = "llama3.2:3b"):
        """
        Initialize the Generation agent with Ollama

        Args:
            base_url: Ollama API base URL
            model: Model to use (llama2, mistral, etc.)
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

    def format_vector_context(self, chunks: List[Dict], max_chunks: int = 5) -> str:
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

        fact_parts = []

        for fact in facts[:max_facts]:
            if fact.get('type') == 'path':
                # Format path
                path_info = f"• {fact['from']} ile {fact['to']} arasında bağlantı bulundu"
                fact_parts.append(path_info)
            else:
                # Format relationship
                source = fact.get('source_entity', '')
                target = fact.get('target_entity', '')
                rel = fact.get('relationship', '')

                fact_parts.append(f"• {source} → [{rel}] → {target}")

        return "\n".join(fact_parts)

    def _format_conversation_history(self, messages: List[Dict]) -> str:
        """
        Format conversation history for prompt inclusion.

        Args:
            messages: List of message dicts with 'sender' and 'content' keys

        Returns:
            Formatted history string or empty string
        """
        if not messages:
            return ""

        history_parts = ["## Önceki Konuşma Bağlamı:"]
        for msg in messages:
            role = "Kullanıcı" if msg.get('sender') == 'user' else "Asistan"
            content = msg.get('content', '')
            # Truncate long messages to save context window
            if len(content) > 200:
                content = content[:200] + "..."
            history_parts.append(f"**{role}**: {content}")

        return "\n".join(history_parts) + "\n"

    def build_prompt(self, query: str, context: Dict,
                     conversation_history: List[Dict] = None) -> str:
        """
        Build the complete prompt for the LLM

        Args:
            query: User's question
            context: Retrieved context (vector + graph)
            conversation_history: Optional list of previous messages

        Returns:
            Complete prompt string
        """
        vector_context = self.format_vector_context(context.get('vector_context', []))
        graph_context = self.format_graph_context(context.get('graph_facts', []))
        history_section = self._format_conversation_history(conversation_history)

        prompt = f"""<|system|>
Sen Türk sağlık sigortası konusunda uzman bir asistansın. Aşağıdaki bilgileri kullanarak soruyu yanıtla.

KURALLAR:
- Sadece verilen kaynaklara dayanarak yanıt ver
- Bilgi yoksa "Bu konuda yeterli bilgim yok" de
- Konuşma geçmişindeki bağlamı dikkate al
- Kısa ve net yanıtla, gerekirse madde işaretleri kullan
- Kaynaklara atıfta bulun
<|end|>

<|context|>
## İlgili Belge Parçaları:
{vector_context}

## Bilgi Grafiğinden İlişkiler:
{graph_context}
<|end|>

{history_section}
<|user|>
{query}
<|end|>

<|assistant|>
"""

        return prompt

    def generate_answer(self, query: str, context: Dict,
                       temperature: float = 0.3,
                       max_tokens: int = 1000,
                       conversation_history: List[Dict] = None) -> str:
        """
        Generate answer using Ollama LLM

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

        # Build the prompt
        prompt = self.build_prompt(query, context, conversation_history)

        try:
            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                },
                timeout=120  # 2 minutes timeout for generation
            )

            if response.status_code == 200:
                result = response.json()
                answer = result.get('response', '')
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
        Generate answer with source citations

        Args:
            query: User's question
            context: Retrieved context
            conversation_history: Optional previous messages for context

        Returns:
            Dictionary with answer and citations
        """
        answer = self.generate_answer(query, context,
                                      conversation_history=conversation_history)

        # Extract top sources for citations
        citations = []
        for chunk in context.get('vector_context', [])[:3]:
            citation = {
                'source': chunk.get('source_name', 'Bilinmeyen'),
                'text': chunk.get('chunk_text', ''),
                'type': chunk.get('document_type', 'PDF'),
                'similarity': chunk.get('similarity', 0)
            }

            # Add ce_score if available
            if 'ce_score' in chunk:
                citation['ce_score'] = chunk.get('ce_score')
            else:
                citation['ce_score'] = "N/A"

            citations.append(citation)

        return {
            'answer': answer,
            'citations': citations,
            'graph_facts_used': len(context.get('graph_facts', []))
        }

    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        Generate a summary of a text

        Args:
            text: Text to summarize
            max_length: Maximum summary length in words

        Returns:
            Summary
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"Aşağıdaki metni {max_length} kelime ile özetle:\n\n{text}",
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('response', text[:500] + "...")
            else:
                print(f"Error generating summary: API returned {response.status_code}")
                return text[:500] + "..."  # Fallback to truncation

        except Exception as e:
            print(f"Error generating summary: {e}")
            return text[:500] + "..."  # Fallback to truncation

    def chat_completion(self, messages: List[Dict],
                       temperature: float = 0.3,
                       max_tokens: int = 1000) -> str:
        """
        Chat completion interface compatible with OpenAI-style messages

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Model temperature
            max_tokens: Maximum response length

        Returns:
            Generated response
        """
        # Convert messages to a single prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")

        prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                raise Exception(f"API returned status {response.status_code}")

        except Exception as e:
            raise Exception(f"Chat completion failed: {str(e)}")

    def generate_streaming(self, prompt: str, max_tokens: int = 1000):
        """
        Generate answer with streaming response.
        Each Ollama streaming line is JSON: {"response": "token", "done": false}
        This method yields only the text tokens.

        Args:
            prompt: Prompt string
            max_tokens: Maximum number of tokens to generate

        Yields:
            Text chunks (individual tokens/words)
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": max_tokens,
                    }
                },
                stream=True,
                timeout=120
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            token = data.get('response', '')
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
            else:
                raise Exception(f"Ollama API returned status {response.status_code}")

        except Exception as e:
            print(f"Error during streaming generation: {e}")
            raise
