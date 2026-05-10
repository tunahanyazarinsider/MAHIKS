"""
Base class for Knowledge Graph extractors.

Subclasses implement only the provider-specific LLM call by overriding
`_generate_triplets_json`. Everything else (chunking, retry/backoff,
JSON parsing, dedup, batch insert into Neo4j, stats) lives here.
"""
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.agents.client.BaseLLMClient import BaseLLMClient
from backend.database.neo4j_handler import Neo4jHandler


class Triplet(BaseModel):
    """Knowledge-graph triplet (subject, predicate, object)."""
    subject: str = Field(description="The primary entity (noun)")
    predicate: str = Field(description="The relationship or action in UPPER_SNAKE_CASE")
    object: str = Field(description="The target entity or value")


KG_SYSTEM_PROMPT = """Sen Türkçe medikal ve sigorta metinlerinden bilgi grafiği oluşturan bir uzmansın.

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


KG_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "triplets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject":   {"type": "string", "description": "The primary entity (noun)"},
                    "predicate": {"type": "string", "description": "The relationship or action in UPPER_SNAKE_CASE"},
                    "object":    {"type": "string", "description": "The target entity or value"},
                },
                "required": ["subject", "predicate", "object"],
            },
        }
    },
    "required": ["triplets"],
}


class KGExtractor():
    """Abstract base for KG extractors. Subclasses override `_generate_triplets_json`."""

    def __init__(self, llm_client : BaseLLMClient, neo4j_handler: Neo4jHandler):
        self.llm : BaseLLMClient = llm_client
        self.neo4j: Neo4jHandler = neo4j_handler
        self.system_prompt: str = KG_SYSTEM_PROMPT
        print(
            f"✓ KGExtractor initialized "
            f"(provider={llm_client.__class__.__name__}, model={llm_client.model})"
        )
    
    @property
    def model(self) -> str:
        return self.llm.model

    def _generate_triplets_json(self, text: str) -> str:
        """Call the LLM to extract triplets as JSON."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Metinden tripletleri çıkar:\n\n{text}"},
        ]
        # Use chat_json for providers that support native JSON mode
        return self.llm.chat_json(messages, temperature=0.1, max_tokens=2000)

    def _extract_triplets(self, text: str, retries: int = 3) -> List[Triplet]:
        for attempt in range(retries):
            try:
                raw: str = self._generate_triplets_json(text)
                data = json.loads(raw)
                print(f"      Extracted {len(data.get('triplets', []))} triplets from chunk (raw JSON length: {len(raw)})")
                print(f"      Sample triplet (if any): {data.get('triplets', [])[0] if data.get('triplets') else 'N/A'}")
                return [
                    Triplet(**t) for t in data.get("triplets", [])
                    if all(k in t for k in ("subject", "predicate", "object"))
                ]
            except Exception as e:
                print(f"      ⚠ KG Extractor attempt {attempt+1}/{retries}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return []

    def _populate_graph(self, text: str, chunk_size: int = 3000,
                        progress_callback: Optional[Callable[[int, int, int], None]] = None) -> int:
        print(f"    Extracting relationships using ({self.model})...")

        chunks: List[str] = self._split_text(text, chunk_size)
        total_chunks: int = len(chunks)
        all_triplets: List[Triplet] = []
        seen = set()

        for i, chunk in enumerate(chunks):
            if total_chunks > 1:
                print(f"      Processing chunk {i+1}/{total_chunks}...")

            for t in self._extract_triplets(chunk):
                key = (t.subject.lower(), t.predicate.lower(), t.object.lower())
                if key not in seen:
                    seen.add(key)
                    all_triplets.append(t)

            if progress_callback:
                progress_callback(i + 1, total_chunks, len(all_triplets))

        batch = [
            (t.subject, t.predicate, t.object) for t in all_triplets
            if len(t.subject) > 2 and len(t.object) > 2
        ]

        if batch:
            self.neo4j.batch_create_triplets(batch)

        print(f"      ✓ Extracted and stored {len(batch)} triplets")
        return len(batch)

    def process_document(self, text: str,
                         progress_callback: Optional[Callable[[int, int, int], None]] = None) -> Dict:
        chunk_size: int = int(os.getenv("KG_CHUNK_SIZE", "3000"))
        triplets_count: int = self._populate_graph(text, chunk_size, progress_callback)
        return {
            "triplets_extracted": triplets_count,
            "model": self.model,
        }

    @staticmethod
    def _split_text(text: str, chunk_size: int) -> List[str]:
        if len(text) <= chunk_size:
            return [text]

        chunks: List[str] = []
        current_chunk: str = ""
        sentences: List[str] = text.replace("! ", "!|").replace("? ", "?|").replace(". ", ".|").split("|")

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
