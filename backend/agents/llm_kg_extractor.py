"""
LLM-based Knowledge Graph Extractor for MAHIKS-TR
Uses Gemini Flash for triplet extraction from medical/insurance texts
Based on proven working approach
"""
from typing import List, Dict
from pydantic import BaseModel, Field
from google import genai
import os


class Triplet(BaseModel):
    """Simple triplet structure"""
    subject: str = Field(description="The primary entity (noun)")
    predicate: str = Field(description="The relationship or action in UPPER_SNAKE_CASE")
    object: str = Field(description="The target entity or value")


class KnowledgeGraph(BaseModel):
    """Knowledge graph response structure"""
    triplets: List[Triplet]


class LLMKnowledgeGraphExtractor:
    """LLM-based knowledge graph extractor using Gemini"""

    def __init__(self, neo4j_handler, api_key: str = None):
        """
        Initialize LLM-based extractor

        Args:
            neo4j_handler: Instance of Neo4jHandler
            api_key: Gemini API key (or set GEMINI_API_KEY or GOOGLE_API_KEY env var)
        """
        self.neo4j = neo4j_handler

        # Get API key from parameter or environment
        api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not found in environment variables")

        # Initialize Gemini client
        self.client = genai.Client(api_key=api_key)

        print("✓ LLM Knowledge Graph Extractor initialized with Gemini")

        # Turkish medical domain prompt
        self.system_prompt = """Sen Türkçe medikal ve sigorta metinlerinden bilgi grafiği oluşturan bir uzmansın.

Metinden tüm önemli varlıkları (entities) ve aralarındaki ilişkileri (relationships) çıkar.

KURALLAR:
1. Her ilişki (subject, predicate, object) formatında triplet olarak temsil edilmeli
2. predicate UPPER_SNAKE_CASE formatında İngilizce olmalı (örn: COVERS, TREATS, REQUIRES, CAUSED_BY, USED_FOR)
3. subject ve object Türkçe olabilir, normalize edilmiş forma getir (örn: "SGK'nın" -> "SGK", "hastalığın" -> "hastalık")
4. Hem açık hem de örtük ilişkileri çıkar
5. Her triplet anlamlı ve doğrulanabilir olmalı
6. Medikal terimleri tam ve doğru kullan
7. Gereksiz kısa veya belirsiz triplet'ler oluşturma

ÖNEMLİ İLİŞKİ TÜRLERİ:
- COVERS, PAYS_FOR, REIMBURSES (kapsam/ödeme)
- TREATS, CURES, PRESCRIBED_FOR (tedavi)
- CAUSES, LEADS_TO, PREVENTS (nedensellik)
- REQUIRES, NEEDS, DEPENDS_ON (gereklilik)
- USED_FOR, APPLIED_TO, ADMINISTERED_TO (kullanım)
- DIAGNOSES, INDICATES, DETECTS (tanı)
- HAS_SYMPTOM, HAS_SIDE_EFFECT, HAS_PROPERTY (özellik)
- IS_A, PART_OF, BELONGS_TO (hiyerarşi)
- PERFORMED_ON, APPLIED_TO (prosedür)
- REQUIRED_BEFORE, CONTRAINDICATED_WITH (koşul)

ÖRNEKLER:

Metin: "SGK kronik hastalıkların tedavisini kapsar."
Triplets:
- (SGK, COVERS, kronik hastalık tedavisi)
- (SGK, PAYS_FOR, kronik hastalık tedavisi)

Metin: "Diyabet için insülin kullanılır."
Triplets:
- (insülin, USED_FOR, diyabet)
- (insülin, TREATS, diyabet)

Metin: "Ameliyat öncesi hastanın kan testi yapılmalıdır."
Triplets:
- (kan testi, REQUIRED_BEFORE, ameliyat)
- (kan testi, PERFORMED_ON, hasta)

Sadece triplet listesini döndür, başka açıklama ekleme."""

    def extract_triplets(self, text: str) -> List[Triplet]:
        """
        Extract knowledge graph triplets from text

        Args:
            text: Input text

        Returns:
            List of Triplet objects
        """
        try:
            prompt = f"{self.system_prompt}\n\n---\n\nMetinden tripletleri çıkar:\n\n{text}"

            # Use Gemini with structured output
            response = self.client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': KnowledgeGraph,
                }
            )

            # Get parsed response
            kg = response.parsed
            return kg.triplets

        except Exception as e:
            print(f"      ⚠ Error extracting triplets: {e}")
            return []

    def populate_graph(self, text: str, chunk_size: int = 3000) -> int:
        """
        Extract triplets and populate Neo4j graph

        Args:
            text: Source text
            chunk_size: Maximum characters per chunk

        Returns:
            Number of triplets created
        """
        print("    Extracting relationships using Gemini LLM...")

        # Split text into chunks if needed
        chunks = self._split_text(text, chunk_size)
        all_triplets = []

        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                print(f"      Processing chunk {i+1}/{len(chunks)}...")

            triplets = self.extract_triplets(chunk)
            all_triplets.extend(triplets)

        # Remove duplicates
        unique_triplets = []
        seen = set()
        for t in all_triplets:
            key = (t.subject.lower(), t.predicate.lower(), t.object.lower())
            if key not in seen:
                seen.add(key)
                unique_triplets.append(t)

        # Insert into Neo4j
        created_count = 0
        for triplet in unique_triplets:
            try:
                # Filter out very short triplets
                if len(triplet.subject) > 2 and len(triplet.object) > 2:
                    self.neo4j.create_triplet(
                        subject=triplet.subject,
                        predicate=triplet.predicate,
                        obj=triplet.object,
                        subject_type="Entity",
                        object_type="Entity"
                    )
                    created_count += 1
            except Exception as e:
                print(f"      ⚠ Error creating triplet ({triplet.subject}, {triplet.predicate}, {triplet.object}): {e}")

        print(f"      ✓ Extracted and stored {created_count} triplets")
        return created_count

    def process_document(self, text: str) -> Dict:
        """
        Process entire document

        Args:
            text: Document text

        Returns:
            Statistics dictionary
        """
        triplets_count = self.populate_graph(text)

        return {
            'triplets_extracted': triplets_count,
            'method': 'LLM-based',
            'model': os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        }

    def _split_text(self, text: str, chunk_size: int) -> List[str]:
        """
        Split text into chunks at sentence boundaries

        Args:
            text: Input text
            chunk_size: Maximum chunk size in characters

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        current_chunk = ""

        # Simple Turkish sentence splitter
        sentences = text.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|')

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
