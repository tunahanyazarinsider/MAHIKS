"""
Local LLM-based Knowledge Graph Extractor for MAHIKS-TR
Uses Ollama (local) for triplet extraction - no external API calls needed.
Handles large documents (250+ pages) reliably.
"""
from typing import List, Dict, Callable, Optional
from pydantic import BaseModel, Field
import requests
import json
import os
import time


class Triplet(BaseModel):
    """Simple triplet structure"""
    subject: str = Field(description="The primary entity (noun)")
    predicate: str = Field(description="The relationship or action in UPPER_SNAKE_CASE")
    object: str = Field(description="The target entity or value")


class LocalKGExtractor:
    """Local LLM-based knowledge graph extractor using Ollama.
    No external API calls - runs entirely on the local machine."""

    def __init__(self, neo4j_handler,
                 base_url: str = None,
                 model: str = None):
        """
        Initialize local KG extractor with Ollama.

        Args:
            neo4j_handler: Instance of Neo4jHandler
            base_url: Ollama API URL (default from env or http://localhost:11434)
            model: Ollama model to use (default from env or llama3.2:3b)
        """
        self.neo4j = neo4j_handler
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip('/')
        self.model = model or os.getenv("KG_OLLAMA_MODEL", "llama3.2:3b")

        # Test connection
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"✓ Local KG Extractor initialized (Ollama, model={self.model})")
            else:
                print(f"⚠ Warning: Could not connect to Ollama at {self.base_url}")
        except Exception as e:
            print(f"⚠ Warning: Ollama connection test failed: {e}")

        # Same Turkish medical domain prompt as the Gemini version
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

Yanıtını sadece JSON formatında ver. Başka açıklama ekleme.
JSON formatı: {"triplets": [{"subject": "...", "predicate": "...", "object": "..."}]}"""

    def extract_triplets(self, text: str, retries: int = 3) -> List[Triplet]:
        """
        Extract knowledge graph triplets from text using local Ollama /api/chat.

        Args:
            text: Input text chunk
            retries: Number of retry attempts on failure

        Returns:
            List of Triplet objects
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Metinden tripletleri çıkar:\n\n{text}"}
        ]

        for attempt in range(retries):
            try:
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "format": "json",
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 2000,
                        }
                    },
                    timeout=120  # 2 min timeout per chunk
                )

                if response.status_code == 200:
                    result_text = response.json().get('message', {}).get('content', '')
                    try:
                        result = json.loads(result_text)
                        triplets = [
                            Triplet(**t) for t in result.get('triplets', [])
                            if all(k in t for k in ('subject', 'predicate', 'object'))
                        ]
                        return triplets
                    except (json.JSONDecodeError, ValueError) as e:
                        print(f"      ⚠ JSON parse error (attempt {attempt+1}/{retries}): {e}")
                else:
                    print(f"      ⚠ Ollama API error {response.status_code} (attempt {attempt+1}/{retries})")

            except requests.exceptions.Timeout:
                print(f"      ⚠ Timeout (attempt {attempt+1}/{retries})")
            except Exception as e:
                print(f"      ⚠ Error (attempt {attempt+1}/{retries}): {e}")

            # Exponential backoff between retries
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                time.sleep(wait_time)

        return []

    def populate_graph(self, text: str, chunk_size: int = 3000,
                       progress_callback: Callable[[int, int, int], None] = None) -> int:
        """
        Extract triplets and populate Neo4j graph.

        Args:
            text: Source text
            chunk_size: Maximum characters per chunk
            progress_callback: Optional fn(current_chunk, total_chunks, triplets_so_far)

        Returns:
            Number of triplets created
        """
        print(f"    Extracting relationships using local Ollama ({self.model})...")

        # Split text into chunks
        chunks = self._split_text(text, chunk_size)
        total_chunks = len(chunks)
        all_triplets = []
        seen = set()

        for i, chunk in enumerate(chunks):
            if total_chunks > 1:
                print(f"      Processing chunk {i+1}/{total_chunks}...")

            triplets = self.extract_triplets(chunk)

            for t in triplets:
                key = (t.subject.lower(), t.predicate.lower(), t.object.lower())
                if key not in seen:
                    seen.add(key)
                    all_triplets.append(t)

            if progress_callback:
                progress_callback(i + 1, total_chunks, len(all_triplets))

        # Batch insert into Neo4j
        batch = [
            (t.subject, t.predicate, t.object) for t in all_triplets
            if len(t.subject) > 2 and len(t.object) > 2
        ]

        if batch:
            self.neo4j.batch_create_triplets(batch)

        print(f"      ✓ Extracted and stored {len(batch)} triplets")
        return len(batch)

    def process_document(self, text: str,
                         progress_callback: Callable[[int, int, int], None] = None) -> Dict:
        """
        Process entire document.

        Args:
            text: Document text
            progress_callback: Optional progress callback

        Returns:
            Statistics dictionary
        """
        chunk_size = int(os.getenv("KG_CHUNK_SIZE", "3000"))
        triplets_count = self.populate_graph(text, chunk_size, progress_callback)

        return {
            'triplets_extracted': triplets_count,
            'method': 'Local-LLM',
            'model': self.model
        }

    def _split_text(self, text: str, chunk_size: int) -> List[str]:
        """
        Split text into chunks at sentence boundaries.

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

        # Turkish sentence splitter
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
