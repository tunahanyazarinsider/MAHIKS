"""
Generation Agent for MAHIKS-TR
Responsible for generating answers using LLM with retrieved context
"""
from openai import OpenAI
from typing import Dict, List, Optional
import os


class GenerationAgent:
    """Agent for answer generation using LLM"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize the Generation agent

        Args:
            api_key: OpenAI API key (defaults to env variable)
            model: Model to use (gpt-4, gpt-3.5-turbo, etc.)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("OpenAI API key not provided")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        print(f"✓ Generation agent initialized (model={model})")

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

    def build_prompt(self, query: str, context: Dict) -> str:
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

        prompt = f"""Sen Türk sağlık sigortası konusunda uzman bir asistansın. Görevin kullanıcıların sorularını doğru, anlaşılır ve yardımsever bir şekilde yanıtlamaktır.

Aşağıdaki bilgileri kullanarak kullanıcının sorusunu yanıtla:

## İlgili Belge Parçaları:
{vector_context}

## Bilgi Grafiğinden İlişkiler:
{graph_context}

## Kullanıcı Sorusu:
{query}

## Yanıt Kuralları:
1. Sadece verilen bilgilere dayanarak yanıt ver
2. Eğer bilgi yetersizse veya soruya yanıt bulunamazsa, bunu açıkça belirt
3. Türkçe, anlaşılır ve profesyonel bir dil kullan
4. Önemli detayları eksik bırakma
5. Gerekirse madde madde açıkla
6. Kaynaklara atıfta bulun

Lütfen yanıtını ver:"""

        return prompt

    def generate_answer(self, query: str, context: Dict,
                       temperature: float = 0.3,
                       max_tokens: int = 1000) -> str:
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

        # Build the prompt
        prompt = self.build_prompt(query, context)

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Sen yardımsever ve bilgili bir Türk sağlık sigortası danışmanısın."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            answer = response.choices[0].message.content
            print(f"      ✓ Answer generated ({len(answer)} chars)")

            return answer

        except Exception as e:
            print(f"      ✗ Error generating answer: {e}")
            return f"Üzgünüm, yanıt oluştururken bir hata oluştu: {str(e)}"

    def generate_with_citations(self, query: str, context: Dict) -> Dict:
        """
        Generate answer with source citations

        Args:
            query: User's question
            context: Retrieved context

        Returns:
            Dictionary with answer and citations
        """
        answer = self.generate_answer(query, context)

        # Extract top sources for citations
        citations = []
        for chunk in context.get('vector_context', [])[:3]:
            citations.append({
                'source': chunk.get('source_name', 'Bilinmeyen'),
                'type': chunk.get('document_type', 'PDF'),
                'similarity': chunk.get('similarity', 0)
            })

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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Sen bir metin özetleme asistanısın."
                    },
                    {
                        "role": "user",
                        "content": f"Aşağıdaki metni {max_length} kelime ile özetle:\n\n{text}"
                    }
                ],
                temperature=0.3
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"Error generating summary: {e}")
            return text[:500] + "..."  # Fallback to truncation
