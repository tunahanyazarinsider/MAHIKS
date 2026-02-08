"""
Query Preprocessor for MAHIKS-TR
Normalizes and corrects Turkish medical queries before retrieval
"""
import re
from typing import Dict


class QueryPreprocessor:
    """Preprocesses Turkish queries for better retrieval quality."""

    # Common Turkish medical domain typos
    TYPO_CORRECTIONS: Dict[str, str] = {
        "sigota": "sigorta",
        "sigortaa": "sigorta",
        "sigrota": "sigorta",
        "ameliyet": "ameliyat",
        "ameliyet": "ameliyat",
        "hastahane": "hastane",
        "hastaane": "hastane",
        "hastene": "hastane",
        "dokotor": "doktor",
        "doktar": "doktor",
        "recete": "reçete",
        "recte": "reçete",
        "ilac": "ilaç",
        "ilaci": "ilacı",
        "muayne": "muayene",
        "muayane": "muayene",
        "muayna": "muayene",
        "labaratuvar": "laboratuvar",
        "labratuvar": "laboratuvar",
        "labartuar": "laboratuvar",
        "radyaloji": "radyoloji",
        "radyaloji": "radyoloji",
        "rontgen": "röntgen",
        "tomago": "tomografi",
        "tomagrofi": "tomografi",
        "endoskapi": "endoskopi",
        "ultrasan": "ultrason",
        "operasyan": "operasyon",
        "ameliyyat": "ameliyat",
        "hastalik": "hastalık",
        "tedavı": "tedavi",
        "tedavii": "tedavi",
        "saglik": "sağlık",
        "saglık": "sağlık",
        "saglk": "sağlık",
        "raporu": "raporu",
        "hekim": "hekim",
        "hekm": "hekim",
        "poliklinik": "poliklinik",
        "poliklink": "poliklinik",
        "acıl": "acil",
        "yogunbakim": "yoğun bakım",
        "yogun bakim": "yoğun bakım",
        "katılım": "katılım",
        "katilim": "katılım",
        "katilm": "katılım",
        "kapsam": "kapsam",
        "kapsamı": "kapsamı",
        "prim": "prim",
        "primm": "prim",
    }

    def __init__(self):
        print("✓ Query preprocessor initialized")

    def preprocess(self, query: str) -> str:
        """
        Full preprocessing pipeline.

        Args:
            query: Raw user query

        Returns:
            Preprocessed query
        """
        query = self.normalize_whitespace(query)
        query = self.fix_typos(query)
        return query

    def fix_typos(self, text: str) -> str:
        """
        Fix common Turkish medical domain typos.

        Args:
            text: Input text

        Returns:
            Text with typos corrected
        """
        words = text.split()
        corrected = []
        for word in words:
            lower = word.lower()
            if lower in self.TYPO_CORRECTIONS:
                corrected.append(self.TYPO_CORRECTIONS[lower])
            else:
                corrected.append(word)
        return " ".join(corrected)

    def normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace.

        Args:
            text: Input text

        Returns:
            Text with normalized whitespace
        """
        return re.sub(r'\s+', ' ', text).strip()
