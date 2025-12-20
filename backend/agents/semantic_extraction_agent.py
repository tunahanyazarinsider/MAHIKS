"""
SUT Structure-Aware Chunker for MAHIKS-TR
==========================================

This module provides intelligent chunking for SUT (Sağlık Uygulama Tebliği)
documents that respects the legal document hierarchy.

Hierarchy Levels:
    Level 1: BÖLÜM (BİRİNCİ BÖLÜM, İKİNCİ BÖLÜM, etc.)
    Level 2: X.Y (1.1, 1.2, 2.1, etc.)
    Level 3: X.Y.Z (1.4.1, 2.2.1, etc.)
    Level 4: X.Y.Z.A (1.4.1.A, 2.2.1.B, etc.)
    Level 5: X.Y.Z.A-N (1.5.1.A-1, 2.2.1.B-2, etc.)
    Level 6: (N) Fıkra - (1), (2), (3)
    Level 7: a) Bent - a), b), c)
    Level 8: N) Alt Bent - 1), 2), 3)

Author: MAHIKS-TR Project
Version: 1.0
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field


# =============================================================================
# CONFIGURATION
# =============================================================================

# Chunk size limits (optimized for 512-token embedding models)
DEFAULT_MAX_WORDS = 350      # Maximum words per chunk
DEFAULT_MIN_WORDS = 50       # Minimum words per chunk
DEFAULT_OVERLAP_WORDS = 30   # Overlap between chunks (optional)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ChunkMetadata:
    """
    Metadata for a single chunk.
    
    This information is crucial for:
    - Retrieval filtering (by section, level)
    - Context reconstruction
    - Citation generation
    """
    section_number: str           # "1.4.1.A", "2.2.1.B-2", etc.
    section_title: str            # "Birinci basamak resmi sağlık hizmeti sunucuları"
    level: int                    # 2, 3, 4, or 5
    parent_chain: List[str]       # ["1.4", "1.4.1"] for context
    bolum: Optional[str] = None   # "BİRİNCİ BÖLÜM" if detected
    fikra: Optional[str] = None   # "1", "2", etc. if chunk is from a specific fıkra
    chunk_type: str = "full"      # "full_section", "fikra", "sentence_split"
    chunk_index: int = 0          # For split chunks: 0, 1, 2...


# =============================================================================
# MAIN CHUNKER CLASS
# =============================================================================

class SUTChunker:
    """
    Structure-aware chunker for SUT (Sağlık Uygulama Tebliği) documents.
    
    This chunker:
    1. Detects section boundaries (1.4.1.A, 2.2.1.B-2, etc.)
    2. Preserves document hierarchy
    3. Adds parent context to each chunk
    4. Splits large sections at fıkra or sentence boundaries
    5. Ensures chunks fit within embedding model token limits
    
    Usage:
        chunker = SUTChunker(max_words=350)
        chunks = chunker.chunk_document(document_text)
        
        for chunk in chunks:
            print(chunk['text'])
            print(chunk['section_number'])
    """
    
    # -------------------------------------------------------------------------
    # REGEX PATTERNS
    # -------------------------------------------------------------------------
    
    # Pattern to match section headers: 1.1, 1.4.1, 1.4.1.A, 1.5.1.A-1
    SECTION_PATTERN = re.compile(
        r'^[\s]*(\d+\.\d+(?:\.\d+)?(?:\.[A-ZÇĞİÖŞÜ])?(?:-\d+)?)\s*[-–]?\s*(.+?)$',
        re.MULTILINE
    )
    
    # Pattern to match BÖLÜM headers
    BOLUM_PATTERN = re.compile(
        r'(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU)\s+BÖLÜM',
        re.IGNORECASE
    )
    
    # Pattern to match fıkra markers: (1), (2), (3)
    FIKRA_PATTERN = re.compile(
        r'^\s*\((\d+)\)\s+',
        re.MULTILINE
    )
    
    # Pattern to match bent markers: a), b), c)
    BENT_PATTERN = re.compile(
        r'^\s*([a-zçğıöşü])\)\s+',
        re.MULTILINE
    )
    
    # Pattern to match EK (appendix) headers
    EK_PATTERN = re.compile(
        r'EK[-\s]*(\d+(?:/[A-ZÇĞİÖŞÜ])?(?:-\d+)?)',
        re.IGNORECASE
    )
    
    # -------------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------------
    
    def __init__(
        self,
        max_words: int = DEFAULT_MAX_WORDS,
        min_words: int = DEFAULT_MIN_WORDS,
        include_context: bool = True,
        context_max_length: int = 60
    ):
        """
        Initialize the chunker.
        
        Args:
            max_words: Maximum words per chunk. 
                       Use 350 for 512-token models (like paraphrase-multilingual-mpnet).
                       Use 800 for 8192-token models (like BGE-M3).
            
            min_words: Minimum words per chunk. Chunks smaller than this
                       will be merged with neighbors or discarded.
            
            include_context: If True, prepend parent section info to each chunk.
                            This helps retrieval but increases chunk size.
            
            context_max_length: Maximum characters for each context line.
                               Prevents very long titles from bloating chunks.
        """
        self.max_words = max_words
        self.min_words = min_words
        self.include_context = include_context
        self.context_max_length = context_max_length
        
        # Internal state
        self._section_titles: Dict[str, str] = {}
        self._current_bolum: Optional[str] = None
    
    # -------------------------------------------------------------------------
    # LEVEL DETECTION
    # -------------------------------------------------------------------------
    
    def detect_level(self, section_num: str) -> int:
        """
        Determine the hierarchy level of a section number.
        
        Args:
            section_num: The section number string (e.g., "1.4.1.A-1")
        
        Returns:
            Integer level (2-5) or 0 if unknown
        
        Examples:
            "1.1"       → Level 2 (X.Y)
            "1.4.1"     → Level 3 (X.Y.Z)
            "1.4.1.A"   → Level 4 (X.Y.Z.A)
            "1.5.1.A-1" → Level 5 (X.Y.Z.A-N)
        """
        # Level 5: X.Y.Z.A-N (e.g., 1.5.1.A-1, 2.2.1.B-2)
        if re.match(r'^\d+\.\d+\.\d+\.[A-ZÇĞİÖŞÜ]-\d+$', section_num):
            return 5
        
        # Level 4: X.Y.Z.A (e.g., 1.4.1.A, 2.2.1.B)
        elif re.match(r'^\d+\.\d+\.\d+\.[A-ZÇĞİÖŞÜ]$', section_num):
            return 4
        
        # Level 3: X.Y.Z (e.g., 1.4.1, 2.2.1)
        elif re.match(r'^\d+\.\d+\.\d+$', section_num):
            return 3
        
        # Level 2: X.Y (e.g., 1.1, 2.1)
        elif re.match(r'^\d+\.\d+$', section_num):
            return 2
        
        # Unknown format
        return 0
    
    # -------------------------------------------------------------------------
    # PARENT CHAIN BUILDING
    # -------------------------------------------------------------------------
    
    def get_parent_sections(self, section_num: str) -> List[str]:
        """
        Get all parent section numbers for building context chain.
        
        Args:
            section_num: The section number (e.g., "1.5.1.A-1")
        
        Returns:
            List of parent section numbers, from highest to lowest level
        
        Example:
            Input:  "1.5.1.A-1"
            Output: ["1.5", "1.5.1", "1.5.1.A"]
        """
        parents = []
        current = section_num
        
        while True:
            # X.Y.Z.A-N → X.Y.Z.A
            if re.match(r'^\d+\.\d+\.\d+\.[A-ZÇĞİÖŞÜ]-\d+$', current):
                current = re.sub(r'-\d+$', '', current)
                parents.append(current)
            
            # X.Y.Z.A → X.Y.Z
            elif re.match(r'^\d+\.\d+\.\d+\.[A-ZÇĞİÖŞÜ]$', current):
                current = re.sub(r'\.[A-ZÇĞİÖŞÜ]$', '', current)
                parents.append(current)
            
            # X.Y.Z → X.Y
            elif re.match(r'^\d+\.\d+\.\d+$', current):
                current = '.'.join(current.split('.')[:-1])
                parents.append(current)
            
            # X.Y → stop (this is our top level within BÖLÜM)
            else:
                break
        
        # Reverse to get top-down order: ["1.5", "1.5.1", "1.5.1.A"]
        return list(reversed(parents))
    
    def build_context_header(
        self,
        section_num: str,
        section_title: str,
        fikra_num: Optional[str] = None
    ) -> str:
        """
        Build a context header to prepend to chunks.
        
        This header provides hierarchical context so that each chunk
        can be understood independently during retrieval.
        
        Args:
            section_num: Current section number
            section_title: Current section title
            fikra_num: Optional fıkra number if chunk is from specific paragraph
        
        Returns:
            Multi-line context string
        
        Example output:
            [BÖLÜM: BİRİNCİ BÖLÜM]
            [1.5: Sağlık hizmeti sunucularına müracaat ve yükümlülükler]
            [1.5.1: Özel sevk kurallarına tabi olan kişilerin...]
            [SECTION: 1.5.1.A-1 - Hasta kabul işlemleri]
            [FIKRA: (1)]
        """
        if not self.include_context:
            return ""
        
        lines = []
        
        # Add BÖLÜM if known
        if self._current_bolum:
            lines.append(f"[BÖLÜM: {self._current_bolum}]")
        
        # Add parent sections
        parents = self.get_parent_sections(section_num)
        for parent in parents:
            if parent in self._section_titles:
                title = self._section_titles[parent]
                # Truncate long titles
                if len(title) > self.context_max_length:
                    title = title[:self.context_max_length] + "..."
                lines.append(f"[{parent}: {title}]")
        
        # Add current section
        title = section_title
        if len(title) > self.context_max_length:
            title = title[:self.context_max_length] + "..."
        lines.append(f"[SECTION: {section_num} - {title}]")
        
        # Add fıkra if specified
        if fikra_num:
            lines.append(f"[FIKRA: ({fikra_num})]")
        
        return '\n'.join(lines)
    
    # -------------------------------------------------------------------------
    # MAIN CHUNKING METHOD
    # -------------------------------------------------------------------------
    
    def chunk_document(self, text: str) -> List[Dict]:
        """
        Main method: Chunk an entire SUT document.
        
        This method:
        1. Finds all section headers
        2. Extracts content for each section
        3. Splits large sections at fıkra or sentence boundaries
        4. Adds context headers to each chunk
        5. Returns list of chunk dictionaries
        
        Args:
            text: Full document text (extracted from PDF)
        
        Returns:
            List of chunk dictionaries, each containing:
                - text: The chunk text with context header
                - section_number: "1.4.1.A", etc.
                - section_title: Section title
                - level: Hierarchy level (2-5)
                - parent_chain: List of parent section numbers
                - fikra: Fıkra number if applicable
                - word_count: Number of words
                - chunk_type: "full_section", "fikra", or "sentence_split"
                - order: Global chunk order (0, 1, 2, ...)
        """
        # Reset internal state
        self._section_titles = {}
        self._current_bolum = None
        
        # -----------------------------------------------------------------
        # STEP 1: Find all section headers and build title lookup
        # -----------------------------------------------------------------
        
        matches = list(self.SECTION_PATTERN.finditer(text))
        
        if not matches:
            # No sections found - return entire text as one chunk
            return [{
                'text': text,
                'section_number': None,
                'section_title': 'Document',
                'level': 0,
                'parent_chain': [],
                'fikra': None,
                'word_count': len(text.split()),
                'chunk_type': 'full_document',
                'order': 0
            }]
        
        # Build section title lookup
        for m in matches:
            section_num = m.group(1)
            title = m.group(2).strip()
            # Clean up title (remove amendment notes)
            title = re.sub(r'\(Değişik:.*?\)', '', title).strip()
            title = re.sub(r'\(Ek:.*?\)', '', title).strip()
            title = re.sub(r'\(Mülga:.*?\)', '', title).strip()
            self._section_titles[section_num] = title
        
        # -----------------------------------------------------------------
        # STEP 2: Detect BÖLÜM for context
        # -----------------------------------------------------------------
        
        bolum_match = self.BOLUM_PATTERN.search(text[:2000])  # Check first part
        if bolum_match:
            self._current_bolum = bolum_match.group(0)
        
        # -----------------------------------------------------------------
        # STEP 3: Process each section
        # -----------------------------------------------------------------
        
        chunks = []
        
        for i, match in enumerate(matches):
            section_num = match.group(1)
            section_title = self._section_titles.get(section_num, "")
            
            # Get section content (from this header to next header)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            
            # Update BÖLÜM context if we find a new one
            bolum_in_section = self.BOLUM_PATTERN.search(content[:500])
            if bolum_in_section:
                self._current_bolum = bolum_in_section.group(0)
            
            # Chunk this section
            section_chunks = self._chunk_section(
                content=content,
                section_num=section_num,
                section_title=section_title
            )
            
            chunks.extend(section_chunks)
        
        # -----------------------------------------------------------------
        # STEP 4: Filter and finalize
        # -----------------------------------------------------------------
        
        # Filter out chunks that are too small
        final_chunks = []
        for chunk in chunks:
            if chunk['word_count'] >= self.min_words:
                chunk['order'] = len(final_chunks)
                final_chunks.append(chunk)
        
        return final_chunks
    
    # -------------------------------------------------------------------------
    # SECTION CHUNKING
    # -------------------------------------------------------------------------
    
    def _chunk_section(
        self,
        content: str,
        section_num: str,
        section_title: str
    ) -> List[Dict]:
        """
        Chunk a single section, splitting if necessary.
        
        Strategy:
        1. If section fits in max_words → return as single chunk
        2. If section has fıkralar → split at fıkra boundaries
        3. If still too large → split at sentence boundaries
        """
        chunks = []
        
        # Build context header
        context_header = self.build_context_header(section_num, section_title)
        context_words = len(context_header.split()) if context_header else 0
        
        # Calculate effective maximum (account for context)
        effective_max = self.max_words - context_words - 5  # Small buffer
        
        # Check total word count
        content_words = len(content.split())
        
        # -----------------------------------------------------------------
        # Case 1: Section fits in one chunk
        # -----------------------------------------------------------------
        
        if content_words <= effective_max:
            full_text = f"{context_header}\n\n{content}" if context_header else content
            
            chunks.append({
                'text': full_text,
                'section_number': section_num,
                'section_title': section_title,
                'level': self.detect_level(section_num),
                'parent_chain': self.get_parent_sections(section_num),
                'bolum': self._current_bolum,
                'fikra': None,
                'word_count': len(full_text.split()),
                'chunk_type': 'full_section',
                'chunk_index': 0
            })
            
            return chunks
        
        # -----------------------------------------------------------------
        # Case 2: Section too large - try splitting by fıkra
        # -----------------------------------------------------------------
        
        fikra_matches = list(self.FIKRA_PATTERN.finditer(content))
        
        if fikra_matches:
            # Process each fıkra
            for j, fm in enumerate(fikra_matches):
                fikra_start = fm.start()
                fikra_end = fikra_matches[j + 1].start() if j + 1 < len(fikra_matches) else len(content)
                fikra_content = content[fikra_start:fikra_end].strip()
                fikra_num = fm.group(1)
                
                # Build fıkra-specific context
                fikra_context = self.build_context_header(
                    section_num, section_title, fikra_num
                )
                fikra_context_words = len(fikra_context.split()) if fikra_context else 0
                fikra_effective_max = self.max_words - fikra_context_words - 5
                
                fikra_words = len(fikra_content.split())
                
                if fikra_words <= fikra_effective_max:
                    # Fıkra fits in one chunk
                    full_text = f"{fikra_context}\n\n{fikra_content}" if fikra_context else fikra_content
                    
                    chunks.append({
                        'text': full_text,
                        'section_number': section_num,
                        'section_title': section_title,
                        'level': self.detect_level(section_num),
                        'parent_chain': self.get_parent_sections(section_num),
                        'bolum': self._current_bolum,
                        'fikra': fikra_num,
                        'word_count': len(full_text.split()),
                        'chunk_type': 'fikra',
                        'chunk_index': 0
                    })
                else:
                    # Fıkra too large - split by sentences
                    sentence_chunks = self._split_by_sentences(
                        text=fikra_content,
                        section_num=section_num,
                        section_title=section_title,
                        context_header=fikra_context,
                        fikra_num=fikra_num
                    )
                    chunks.extend(sentence_chunks)
        
        else:
            # No fıkralar - split entire section by sentences
            sentence_chunks = self._split_by_sentences(
                text=content,
                section_num=section_num,
                section_title=section_title,
                context_header=context_header,
                fikra_num=None
            )
            chunks.extend(sentence_chunks)
        
        return chunks
    
    # -------------------------------------------------------------------------
    # SENTENCE-LEVEL SPLITTING
    # -------------------------------------------------------------------------
    
    def _split_by_sentences(
        self,
        text: str,
        section_num: str,
        section_title: str,
        context_header: str,
        fikra_num: Optional[str] = None
    ) -> List[Dict]:
        """
        Split text at sentence boundaries when it's too large.
        
        This is the last resort when sections and fıkralar are still too large.
        """
        chunks = []
        
        # Split into sentences (Turkish sentence endings)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Calculate effective maximum
        context_words = len(context_header.split()) if context_header else 0
        effective_max = self.max_words - context_words - 5
        
        current_chunk_sentences = []
        current_word_count = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_words = len(sentence.split())
            
            # Check if adding this sentence would exceed limit
            if current_word_count + sentence_words > effective_max and current_chunk_sentences:
                # Save current chunk
                chunk_text = ' '.join(current_chunk_sentences)
                full_text = f"{context_header}\n\n{chunk_text}" if context_header else chunk_text
                
                chunks.append({
                    'text': full_text,
                    'section_number': section_num,
                    'section_title': section_title,
                    'level': self.detect_level(section_num),
                    'parent_chain': self.get_parent_sections(section_num),
                    'bolum': self._current_bolum,
                    'fikra': fikra_num,
                    'word_count': len(full_text.split()),
                    'chunk_type': 'sentence_split',
                    'chunk_index': chunk_index
                })
                
                # Reset for next chunk
                current_chunk_sentences = []
                current_word_count = 0
                chunk_index += 1
            
            # Add sentence to current chunk
            current_chunk_sentences.append(sentence)
            current_word_count += sentence_words
        
        # Don't forget the last chunk
        if current_chunk_sentences:
            chunk_text = ' '.join(current_chunk_sentences)
            full_text = f"{context_header}\n\n{chunk_text}" if context_header else chunk_text
            
            chunks.append({
                'text': full_text,
                'section_number': section_num,
                'section_title': section_title,
                'level': self.detect_level(section_num),
                'parent_chain': self.get_parent_sections(section_num),
                'bolum': self._current_bolum,
                'fikra': fikra_num,
                'word_count': len(full_text.split()),
                'chunk_type': 'sentence_split',
                'chunk_index': chunk_index
            })
        
        return chunks
    
    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------
    
    def get_statistics(self, chunks: List[Dict]) -> Dict:
        """
        Get statistics about chunking results.
        
        Useful for debugging and optimization.
        """
        if not chunks:
            return {'total_chunks': 0}
        
        word_counts = [c['word_count'] for c in chunks]
        levels = [c['level'] for c in chunks]
        chunk_types = [c['chunk_type'] for c in chunks]
        
        return {
            'total_chunks': len(chunks),
            'total_words': sum(word_counts),
            'avg_words': sum(word_counts) / len(word_counts),
            'min_words': min(word_counts),
            'max_words': max(word_counts),
            'level_distribution': {
                f'level_{l}': levels.count(l) 
                for l in sorted(set(levels))
            },
            'type_distribution': {
                t: chunk_types.count(t) 
                for t in set(chunk_types)
            },
            'sections_covered': len(set(c['section_number'] for c in chunks if c['section_number']))
        }


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def chunk_sut_document(
    text: str,
    max_words: int = 350,
    include_context: bool = True
) -> List[Dict]:
    """
    Convenience function to chunk a SUT document.
    
    Args:
        text: Full document text
        max_words: Maximum words per chunk (350 for 512-token models)
        include_context: Include parent section info in chunks
    
    Returns:
        List of chunk dictionaries
    
    Usage:
        from sut_chunker import chunk_sut_document
        
        with open('sut.txt', 'r') as f:
            text = f.read()
        
        chunks = chunk_sut_document(text)
        
        for chunk in chunks:
            # Store in database
            db.insert_chunk(
                text=chunk['text'],
                section=chunk['section_number'],
                metadata=chunk
            )
    """
    chunker = SUTChunker(
        max_words=max_words,
        include_context=include_context
    )
    return chunker.chunk_document(text)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    """
    Example usage - run this file directly to test.
    
    Usage:
        python sut_chunker.py path/to/sut.txt
    
    Or in Python:
        from sut_chunker import SUTChunker
        
        chunker = SUTChunker(max_words=350)
        chunks = chunker.chunk_document(document_text)
    """
    import sys
    
    # Check if file path provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        # Use sample text for testing
        text = """
        1.1 - Amaç
(1) Tebliğin amacı (bundan sonra SUT olarak ifade edilecektir); sağlık yardımları Sosyal
Güvenlik Kurumunca (bundan sonra Kurum olarak ifade edilecektir) karşılanan ve kapsam
maddesinde tanımlanan kişilerin, (Ek ibare:RG-18/2/2017-29983)(80) sağlıklı kalmalarını,
hastalanmaları halinde sağlıklarını kazanmalarını, iş kazası ile meslek hastalığı, hastalık ve analık
sonucu tıbben gerekli görülen sağlık hizmetlerinin karşılanmasını, iş göremezlik hallerinin
ortadan kaldırılmasını veya azaltılmasını temin etmek amacıyla Kurumca finansmanı sağlanan
sağlık hizmetleri, yol, gündelik ve refakatçi giderlerinden yararlanma esas ve usulleri ile bu
hizmetlere ilişkin Sağlık Hizmetleri Fiyatlandırma Komisyonunca belirlenen Kurumca ödenecek
bedellerin bildirilmesidir.
1.2 - Kapsam
(1) 5510 sayılı Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu ve diğer kanunlardaki özel
hükümler gereği genel sağlık sigortasından yararlandırılan kişiler.
1.3 - Dayanak
(1) (Değişik:RG-25/8/2022-31934 Mükerrer)(94) SUT; 5502 sayılı Sosyal Güvenlik
Kurumuna İlişkin Bazı Düzenlemeler Hakkında Kanun, 5510 sayılı Kanun ve Genel Sağlık Sigortası
Uygulamaları Yönetmeliği hükümleri çerçevesinde düzenlenmiştir.
1.4 - Sağlık hizmeti sunucuları (Değişik:RG-25/8/2022-31934 Mükerrer) (94)
1.4.1- Birinci basamak sağlık hizmeti sunucuları
1.4.1.A - Birinci basamak resmi sağlık hizmeti sunucuları
1) Bünyesinde birinci basamak sağlık kuruluşu bulunan ilçe sağlık müdürlüğü
2) Toplum sağlığı merkezi (TSM)
3) Aile sağlığı merkezi (ASM)
4) Halk sağlığı laboratuvarı (L1ve L2)
5) Kurum tabipliği
6) 112 Acil sağlık hizmeti birimleri
7) Üniversiteler bünyesindeki mediko-sosyal birimler
8) Türk Silahlı Kuvvetlerinin birinci basamak sağlık üniteleri
9) Belediyelere ait poliklinikler
10) Birinci basamak ayaktan ve yataklı teşhis, tedavi ve rehabilitasyon hizmeti sunan sağlık
hizmeti sunucuları entegre ilçe devlet hastaneleridir (E2 ve E3)
1.4.1.B - Birinci basamak özel sağlık hizmeti sunucuları
1) Evde bakım merkezleri veya birimler
2) İşyeri sağlık ve güvenlik hizmeti sunulan birimler
3) Özel poliklinikler
4) Ağız ve diş sağlığı hizmeti veren özel sağlık kuruluşları
5) 18/12/1953 tarihli ve 6197 sayılı Eczacılar ve Eczaneler Hakkında Kanun kapsamında
serbest faaliyet gösteren eczaneler
1.4.2 - İkinci basamak sağlık hizmeti sunucuları
1.4.2.A - İkinci basamak resmi sağlık hizmeti sunucuları
1) Eğitim ve araştırma hastanesi olmayan devlet hastaneleri ve dal hastaneleri ile bu
hastanelere bağlı semt poliklinikleri
2) Entegre ilçe hastanesi (E1)
3) Sağlık Bakanlığına bağlı ağız ve diş sağlığı merkezleri (Ek ibare:RG-26/4/2025-32882)(128)
ile ağız ve diş sağlığı hastaneleri
4) (Mülga:RG-26/4/2025-32882)(128)
5) Kamu kurumlarına ait olup Sağlık Bakanlığınca ruhsatlandırılmış olan hastaneler, tıp
merkezleri ve dal merkezleri
6) Kamu kurumlarına ait diyaliz merkezleri, üremeye yardımcı tedavi merkezleri,
hiperbarik oksijen tedavi merkezleri, tıbbi laboratuvarlar gibi müstakil olarak ruhsatlandırılan
tanı ve tedavi merkezleri.
1.4.2.B - İkinci basamak özel sağlık hizmeti sunucuları
1) Özel hastaneler (ÖH)
2) Özel tıp merkezleri ve dal merkezleri
3) Özel Diyaliz merkezleri,
4) Özel üremeye yardımcı tedavi merkezleri
5) Özel hiperbarik oksijen tedavi merkezleri
6) Tıbbi laboratuvarlar gibi müstakil olarak ruhsatlandırılan özel tanı ve tedavi
merkezleri.
1.4.3 - Üçüncü basamak sağlık hizmeti sunucuları
1.4.3.A - Üçüncü basamak resmi sağlık hizmeti sunucuları
1) Sağlık Bakanlığına bağlı eğitim ve araştırma hastaneleri ile bu hastanelere bağlı semt
poliklinikleri
2) Tıp Fakülteleri Bulunan Devlet Üniversiteleri Sağlık Uygulama ve Araştırma Merkezleri
(U1)
3) Tıp Fakülteleri Bulunan Vakıf Üniversiteleri Sağlık Uygulama ve Araştırma Merkezleri
(U2)
4) (Ek:RG-21/4/2024-32524)(104) Diş hekimliği fakülteleri bulunan Devlet/vakıf üniversite
hastaneleri
5) (Ek:RG-21/4/2024-32524)(104) Sağlık Bakanlığınca üçüncü basamak hastane olarak
basamaklandırılan Sağlık Bakanlığına bağlı hastaneler
1.4.3.B - Üçüncü basamak özel sağlık hizmeti sunucuları
1) Sağlık Bakanlığınca üçüncü basamak hastane olarak basamaklandırılan özel hastaneler
(ÖH)
1.4.4 - Sağlık hizmeti sunumu bakımından basamaklandırılamayan sağlık hizmeti
sunucuları
1) Optisyenlik müesseseleri
2) Tıbbi cihaz ve malzeme tedarikçileri
3) Kaplıcalar
4) Beşeri tıbbi ürün/ürün sunan ve/veya üreten özel hukuk tüzel kişileri ve bunların tüzel
kişiliği olmayan şubeleri
5) Bu maddenin diğer fıkraları ile 1.4.1, 1.4.2, 1.4.3 numaralı maddelerde yer almayan
Sağlık Bakanlığınca ruhsatlandırılmış ve/veya izin verilmiş sağlık hizmet sunumu bakımından
basamaklandırılamayan diğer özelleşmiş tanı ve tedavi ve tedarik merkezleri.
1.4.5 - (Mülga:RG-16/3/2023-32134 Mükerrer)(95)
1.5 - Sağlık hizmeti sunucularına müracaat ve yükümlülükler
(1) Ayakta veya yatarak tanı ve tedavi hizmeti sunan sözleşmeli sağlık hizmeti
sunucularına, sunmuş oldukları sağlık hizmeti bedellerinin ödenebilmesi için müracaat
işlemlerinin aşağıda belirtilen usul ve esaslar doğrultusunda gerçekleştirilmiş olması
gerekmektedir.
1.5.1 - Özel sevk kurallarına tabi olan kişilerin sağlık hizmeti sunucularına müracaat
işlemleri
(1) (Değişik:RG-25/3/2017-30018)(81) 5510 sayılı Kanunun 60 ıncı maddesinin birinci
fıkrasının (c) bendinin (Değişik ibare:RG-9/9/2017-30175)(92) (1) ve (3) numaralı alt bentleri ile
aynı maddenin onikinci, onüçüncü ve ondördüncü fıkraları gereği genel sağlık sigortası
kapsamına alınan kişilerin, ayakta veya yatarak teşhis ve tedavi hizmeti veren sağlık hizmeti
sunucularına müracaatlarında MEDULA sistemi üzerinden müstahaklık sorgulaması yapılır.
Sorgulama sonucu Kurum bilgisi (Değişik ibare:RG-9/9/2017-30175)(92) 60/c-1 veya 60/c-3 dönen
kişiler ile 60 ıncı maddenin onikinci, onüçüncü ve ondördüncü fıkralarında tanımlanan kişilerin
müracaat kabul ve sevk işlemleri aşağıdaki şekilde yürütülecektir. Aşağıda belirtilen usul ve
esaslara uygun olmayan müracaatlara ilişkin sağlık hizmeti bedelleri Kurumca karşılanmaz.
(2) Sağlık hizmeti sunucuları tedavilerinin sağlanamaması halinde kişileri, aşağıdaki
düzenlemelere göre söz konusu tedavi için doğrudan müracaat hakkı bulunduğu sağlık hizmeti
sunucularına sevk de edebilirler.
(3) (Değişik:RG-18/1/2016-29597)(45) Acil haller dışında sözleşmesiz özel sağlık hizmeti
sunucularından alınan sağlık hizmeti bedelleri Kurumca ödenmez. Sözleşmesiz özel sağlık hizmeti
sunucularından acil hallerde alınan sağlık hizmetlerinin bedellerinin ödenebilmesi için bu
durumun Kurum inceleme birimlerince kabul edilmesi gerekmektedir.
1.5.1.A - Sağlık Bakanlığı sağlık hizmeti sunucularınca hasta kabul ve sevk işlemleri
1.5.1.A-1 - Hasta kabul işlemleri
(1) Doğrudan veya sevkli müracaatlar kabul edilir.
1.5.1.A-2 - Hasta sevk işlemleri
(1) Tedavinin sağlanamaması halinde;
a) Birinci basamak sağlık hizmeti sunucularınca; sevkler aynı yerleşim yeri içindeki
Sağlık Bakanlığı ikinci veya üçüncü basamak sağlık hizmeti sunucusuna yapılabilir.
b)İkinci basamak sağlık hizmeti sunucularınca;
1)Kişiler, aynı yerleşim yeri içindeki Sağlık Bakanlığı ikinci veya üçüncü basamak sağlık
hizmeti sunucusuna sevk edilebilir.
2)Kişiler, aynı yerleşim yerinde Sağlık Bakanlığı üçüncü basamak sağlık hizmeti sunucusu
yoksa aynı yerleşim yerindeki diğer resmi sağlık hizmeti sunucularına veya yerleşim yeri dışındaki
Sağlık Bakanlığı ikinci veya üçüncü basamak sağlık hizmeti sunucularına sevk edilebilir.
3) Kişiler, resmi sağlık hizmeti sunucularında uygun yoğun bakım yatağının bulunmaması
ve hasta naklinin 112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştirilmesi koşuluyla
yoğun bakım tedavisi için özel sağlık hizmeti sunucularına da sevk edilebilir. Bu durumda, naklin
112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştiğini gösterir belge yeterli kabul
edilecektir.
4)Kişiler, aynı il içindeki resmi sağlık hizmeti sunucularında tedavinin sağlanabileceği
radyoterapi merkezi bulunmaması halinde radyoterapi tedavisi için aynı il içindeki özel sağlık
hizmeti sunucularına sevk edilebilir.
5) Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına kronik hemodiyaliz
tedavisi programı için yapılacak sevkler, aynı yerleşim yerinde varsa bünyesinde hemodiyaliz
merkezi bulunan Sağlık Bakanlığı sağlık hizmeti sunucularınca yoksa müracaat edilen sağlık
hizmeti sunucusunca yapılacaktır. Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına
yapılan hemodiyaliz amaçlı sevkler 3 ay süre ile geçerli olup sürenin bitiminde sevk belgesinin
yenilenmesi gerekmektedir.
c) Üçüncü basamak sağlık hizmeti sunucularınca;
1)Kişiler, aynı yerleşim yeri içindeki veya dışındaki; Sağlık Bakanlığı ikinci veya üçüncü
basamak sağlık hizmeti sunucusuna veya diğer resmi sağlık hizmeti sunucularına sevk edilebilir.
2)Kişiler, resmi sağlık hizmeti sunucularında uygun yoğun bakım yatağının bulunmaması ve
hasta naklinin 112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştirilmesi koşuluyla
yoğun bakım tedavisi için özel sağlık hizmeti sunucularına da sevk edilebilir. Bu durumda, naklin
112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştiğini gösterir belge yeterli kabul
edilecektir.
3) Kişiler, aynı il içindeki resmi sağlık hizmeti sunucularında tedavinin sağlanabileceği
radyoterapi merkezi bulunmaması halinde radyoterapi tedavisi için aynı il içindeki özel sağlık
hizmeti sunucularına sevk edilebilir.
4) Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına kronik hemodiyaliz
tedavisi programı için yapılacak sevkler, aynı yerleşim yerinde varsa bünyesinde hemodiyaliz
merkezi bulunan Sağlık Bakanlığı sağlık hizmeti sunucularınca yoksa müracaat edilen sağlık
hizmeti sunucusunca yapılacaktır. Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına
yapılan hemodiyaliz amaçlı sevkler 3 ay süre ile geçerli olup sürenin bitiminde sevk belgesinin
yenilenmesi gerekmektedir.
1.5.1.B - Sağlık Bakanlığı dışındaki üçüncü basamak resmi sağlık hizmeti sunucularınca
hasta kabul ve sevk işlemleri (Değişik başlık:RG-25/8/2022-31934 Mükerrer)(94)
1.5.1.B-1 - Hasta kabul işlemleri
(1) Sağlık Bakanlığı dışındaki üçüncü basamak (Ek ibare:RG-25/8/2022-31934
Mükerrer)(94) resmi sağlık hizmeti sunucularınca aşağıda belirtilen müracaatlar kabul edilir.
a) Sevkli müracaatlar
1) Sağlık Bakanlığı ikinci ve üçüncü basamak sağlık hizmeti sunucularınca SUT’un 1.5.1.A-
2 maddesine uygun olarak düzenlenen sevk belgesi ile müracaat eden hastalar.
2) Sağlık Bakanlığı dışındaki üçüncü basamak (Ek ibare:RG-25/8/2022-31934
Mükerrer)(94) resmi sağlık hizmeti sunucularınca SUT’un 1.5.1.B-2 maddesine uygun olarak
düzenlenen sevk belgesi ile müracaat eden hastalar.
b) Doğrudan müracaatlar
1) Organ, doku ve kök hücre nakline ilişkin; sağlık hizmetleri ve naklin yapıldığı sağlık
hizmeti sunucusundaki kontroller ve devam tedavileri için yapılan müracaatlar.
2) Akkiz immün yetmezlik sendrom tanılı hasta müracaatları.
3) Hiperbarik oksijen tedavisi için yapılan müracaatlar.
4) Trafik kazası nedeniyle yapılan müracaatlar.
5) Acil servis müracaatları (SUT’un 2.3 maddesi hükümleri doğrultusunda işlem
yürütülür).
6) Kurum ile götürü bedel üzerinden sağlık hizmeti alım sözleşmesi imzalanan Sağlık
Bakanlığı dışındaki üçüncü basamak (Ek ibare:RG-25/8/2022-31934 Mükerrer)(94) resmi sağlık
hizmeti sunucularına yapılan müracaatlar.
c) Diğer müracaatlar
1) SUT’un 1.5.1.B-1(1)a bendine göre müracaatları kabul edilen hastaların aynı sağlık
hizmeti sunucusunda diğer branşlarda da muayene veya tedavisinin gerekli görülmesi
durumunda (konsültasyon istemi hariç); branş hekimince aynı sevk belgesi üzerinde
gönderilecek branşın belirtilmesi şartıyla ilgili branşa yapılan müracaatlar. Bu durumda Kurum
bilgi işlem sistemine yeniden sevk beyanı (hastane içi sevk) girilecektir.
2) SUT’un 1.5.1.B-1(1) fıkrasının a ve b bentlerine göre müracaatları kabul edilen
hastalardan çağrı evrakı düzenlenmek suretiyle tedavi veya kontrol amaçlı çağrılanların
müracaatları. (Bu durumda müracaatın çağrıya istinaden yapıldığına dair Kurum bilgi işlem
sistemine beyan girilecektir.)
3) SUT’un 1.5.1.B-1(1) fıkrasının a ve b bentlerine göre müracaatları kabul edilen
hastalardan fizik tedavi ve rehabilitasyon tedavisi, hemodiyaliz tedavisi, radyoterapi ve
kemoterapi gibi belli bir program dahilinde tedavi gören hastaların tedavi süresi içindeki, ilk sevk
belgesine istinaden yapılan müteakip müracaatları. Hemodiyaliz amaçlı sevkler 3 ay süre ile
geçerli olup sürenin bitiminde sevk belgesinin yenilenmesi gerekmektedir.
1.5.1.B-2 - Hasta sevk işlemleri
(1) Tedavinin sağlanamaması halinde;
1) Kişiler, Sağlık Bakanlığı sağlık hizmeti sunucularına sevk edilebilir.
2) Kişiler, Sağlık Bakanlığı dışındaki üçüncü basamak (Ek ibare:RG-25/8/2022-31934
Mükerrer)(94) resmi sağlık hizmeti sunucularına sevk edilebilir.
3) Kişiler, resmi sağlık hizmeti sunucularında uygun yoğun bakım yatağının bulunmaması
ve hasta naklinin 112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştirilmesi koşuluyla
yoğun bakım tedavisi için özel sağlık hizmeti sunucularına da sevk edilebilir. Bu durumda, naklin
112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştiğini gösterir belge yeterli kabul
edilecektir.
4) Kişiler, kronik hemodiyaliz tedavisi programı için aynı yerleşim yerinde varsa
bünyesinde hemodiyaliz merkezi bulunan Sağlık Bakanlığı sağlık hizmeti sunucularına yoksa diğer
resmi sağlık hizmeti sunucularına, yerleşim yeri içinde resmi sağlık hizmeti sunucularınca diyaliz
tedavisinin yapılamaması halinde ise yerleşim yeri dışındaki Sağlık Bakanlığı sağlık hizmeti
sunucularına sevk edilebilir. Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına yapılan
hemodiyaliz amaçlı sevkler 3 ay süre ile geçerlidir.
5) Kişiler, aynı il içindeki resmi sağlık hizmeti sunucularında tedavinin sağlanabileceği
radyoterapi merkezi bulunmaması halinde radyoterapi tedavisi için aynı il içindeki özel sağlık
hizmeti sunucularına sevk edilebilir.
1.5.1.C - Sağlık Bakanlığı dışındaki ikinci basamak resmi sağlık hizmeti sunucularınca
hasta kabul ve sevk işlemleri
1.5.1.C-1 - Hasta kabul işlemleri
(1) Hasta kabul işlemleri yürütümünde aşağıdaki düzenlemelere uyulacaktır.
a) Kurum ile götürü bedel üzerinden sağlık hizmeti alım sözleşmesi imzalanan sağlık
hizmeti sunucularınca (Değişik ibare:RG-4/2/2018-30322)(102) ve belediyelere ait sağlık hizmeti
sunucularınca;
1) Doğrudan veya sevkli müracaatlar kabul edilir.
b) Diğer resmi sağlık hizmeti sunucularınca;
1) Sevkli müracaatlar
aa) SUT’un 1.5.1.A-2 ve 1.5.1.B-2 maddelerine uygun olarak düzenlenen sevk belgesi ile
müracaat eden hastalar.
2) Doğrudan müracaatlar
aa) Organ, doku ve kök hücre nakline ilişkin; sağlık hizmetleri ve naklin yapıldığı sağlık
hizmeti sunucusundaki kontroller ve devam tedavileri için yapılan müracaatlar.
bb) Akkiz immün yetmezlik sendrom tanılı hasta müracaatları.
cc) Hiperbarik oksijen tedavisi için yapılan müracaatlar.
çç) Trafik kazası nedeniyle yapılan müracaatlar.
dd) Acil servis müracaatları (SUT’un 2.3 maddesi hükümleri doğrultusunda işlem
yürütülür.)
1.5.1.C-2 - Hasta sevk işlemleri
(1) Kişiler, resmi sağlık hizmeti sunucularında uygun yoğun bakım yatağının bulunmaması
ve hasta naklinin 112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştirilmesi koşuluyla
yoğun bakım tedavisi için özel sağlık hizmeti sunucularına da sevk edilebilir. Bu durumda, naklin
112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştiğini gösterir belge yeterli kabul
edilecektir.
1.5.1.Ç - Özel sağlık hizmeti sunucularınca hasta kabul ve sevk işlemleri
1.5.1.Ç-1 - Hasta kabul işlemleri
(1) Hasta kabul işlemleri yürütümünde aşağıdaki düzenlemelere uyulacaktır.
a) Sevkli müracaatlar
1) Resmi sağlık hizmeti sunucularında uygun yoğun bakım yatağının bulunmaması ve
hasta naklinin 112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştirilmesi koşuluyla
yoğun bakım tedavisi için gönderilen hastalar. Bu durumda, naklin 112 Komuta Kontrol Merkezi
koordinasyonunda gerçekleştiğini gösterir belge yeterli kabul edilecektir.
2) SUT’un 1.5.1.A-2 ve 1.5.1.B-2 maddelerine uygun olarak düzenlenen sevk belgesi ile
radyoterapi tedavisi için sevk edilen hastalar.
b) Doğrudan müracaatlar
1) (Değişik:RG-18/1/2016-29597) (45) Acil haller nedeniyle yapılan müracaatlar. Hasta
müracaatının söz konusu durum nedeniyle yapıldığının Kurum inceleme birimlerince kabul
edilmesi gerekmektedir.
2) Hiperbarik oksijen tedavisi için yapılan müracaatlar.
3) Trafik kazası nedeniyle yapılan müracaatlar.
1.5.1.Ç-2 - Hasta sevk işlemleri
(1) Kişiler, resmi sağlık hizmeti sunucularında uygun yoğun bakım yatağının bulunmaması
ve hasta naklinin 112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştirilmesi koşuluyla
yoğun bakım tedavisi için özel sağlık hizmeti sunucularına da sevk edilebilir. Bu durumda, naklin
112 Komuta Kontrol Merkezi koordinasyonunda gerçekleştiğini gösterir belge yeterli kabul
edilecektir.
1.5.1.D - Diğer hükümler
(1) Sağlık hizmeti sunucularınca sevkler, Kurum bilgi işlem sistemi üzerinden elektronik
olarak düzenlenmesi sağlanıncaya kadar SUT eki “Hasta Sevk Formu” (EK-2/F) ile veya bu formda
istenilen bilgilerin yer aldığı belge tanzim edilerek yapılacaktır. Düzenlenen sevkin bir örneği
hastaya verilecektir. Sevk belgesinde sevk edilen branş ile birlikte sağlık hizmeti sunucusu adı
mutlaka yer alacaktır. Kişiler sevk belgesi ile sevkin düzenlendiği tarih dahil 5 işgünü içinde sevk
edildikleri sağlık hizmeti sunucusuna müracaat edeceklerdir.
(2) Sevkli müracaatı kabul eden sağlık hizmeti sunucusunca, SUT eki EK-2/F veya bu
formda istenilen bilgilerin yer aldığı belgenin bir örneği fatura ekinde Kuruma gönderilecektir.
Ayrıca SUT’un 1.5 maddesinde hasta müracaatının kabulüne ilişkin düzenleneceği belirtilen diğer
belgelerin (112 Komuta Kontrol Merkezi koordinasyonunu gösterir belge, çağrı evrakı gibi)
düzenlenme ve takip işlemlerinin Kurum bilgi işlem sistemi üzerinden yapılması sağlanıncaya
kadar söz konusu belgelerin bir örneği fatura ekinde Kuruma gönderilecektir.
(3) Sevklerin, Kurum bilgi işlem sistemi üzerinden elektronik olarak düzenlenmesi
uygulamasına geçilmesi halinde yürütülecek işlemler Kurumca ayrıca duyurulur.
(4) Kurum gerekli gördüğü hallerde, Sağlık Bakanlığı dışındaki resmi sağlık hizmeti
sunucuları ile sağlık hizmetinin sunulduğu il, sağlık hizmetinin niteliği itibarıyla hayati öneme
sahip olup olmaması, sağlık hizmeti ihtiyacının resmi sağlık hizmeti sunucularında karşılanıp
karşılanmaması, hizmetin niteliği gibi hususları dikkate alarak özel sağlık hizmeti sunucularına
müracaatlara ilişkin ayrıca usul ve esas belirlemeye yetkilidir.
1.5.2 - Genel sağlık sigortası kapsamındaki diğer kişilerin sağlık hizmeti sunucularına
müracaat işlemleri
(1) Kişiler, SUT’ta belirtilen özel hükümler saklı kalmak kaydıyla Kurum ile sözleşmesi
bulunan ayakta ve yatarak tedavi hizmeti sağlayan sağlık hizmeti sunucularına doğrudan veya
sevk edilmek suretiyle müracaat edebilirler.
(2) Kişilerin, SUT’un 2.2(5) fıkrasında belirtilen istisnalar hariç olmak üzere acil haller
dışında Kurum ile sözleşmesi olmayan sağlık hizmeti sunucularından aldıkları sağlık hizmeti
bedelleri Kurumca karşılanmaz.
(3) Kurum ile sözleşmeli sağlık hizmeti sunucuları, Kurum sağlık yardımlarından
yararlandırılan kişilerin müracaatlarını ayrım yapmaksızın kabul etmek zorundadır.
1.6 - Kimlik tespiti
(1) Sağlık (Değişik ibare:RG-25/8/2022-31934 Mükerrer)(94) hizmeti sunucularınca,
kişilerin müracaatı aşamasında, acil hallerde ise acil halin sona ermesinden sonra, nüfus cüzdanı,
sürücü belgesi, evlenme cüzdanı, pasaport veya verilmiş ise Kurum sağlık kartı belgelerinden biri
ile kimlik tespiti ve biyometrik yöntemlerle kimlik doğrulaması yapılması zorunludur. Kimlik
tespiti, biyometrik kayıt işlemi veya biyometrik kimlik doğrulama işlemini usulüne uygun
yapmayan ve bu nedenle bir başka kişiye sağlık hizmeti sunulması nedeniyle Kurumun zarara
uğramasına sebebiyet veren sağlık hizmeti sunucularından ödenen tutar geri alınır.
(2) 2828 sayılı Sosyal Hizmetler Kanunu kapsamında sağlanan yardımlardan ücretsiz
faydalananların, sağlık (Değişik ibare:RG-25/8/2022-31934 Mükerrer)(94) hizmeti sunucularına
birinci fıkrada belirtilen belgeleri ibraz edememeleri halinde 2828 sayılı Kanun kapsamında
bulunduklarını gösterir belgeye göre gerekli işlemler yürütülecek sonrasında söz konusu
belgelerin ibrazı ilgili Kurumdan istenecektir.
(3) Kapsamdaki kişilerin kendi adına bir başkasının sağlık hizmeti almasını veya Kurumdan
haksız bir menfaat temin etmesini sağlaması yasaktır. Bu fiilleri işleyenlerden Kurumun uğradığı
zararın iki katı kanunî faiziyle birlikte müştereken ve müteselsilen tahsil edilir ve ilgililer hakkında
5237 sayılı Türk Ceza Kanunu hükümleri doğrultusunda suç duyurusunda bulunulur.
1.6.1 - Biyometrik kimlik doğrulama işlemi
(1) Kimlik doğrulamada kullanılacak olan biyometrik sistem ve uygulamaya geçilecek sağlık
hizmeti sunucuları, uygulama tarihi ile uygulamaya ilişkin usul ve esaslar Kurum tarafından
belirlenir.
(2) Kişinin sağlık hizmeti sunucusuna müracaatı sırasında ilk biyometrik
        """
    
    # Create chunker and process
    chunker = SUTChunker(max_words=350, include_context=True)
    chunks = chunker.chunk_document(text)
    print(len(chunks))
    # Print statistics
    stats = chunker.get_statistics(chunks)
    print("=" * 70)
    print("CHUNKING STATISTICS")
    print("=" * 70)
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Total words: {stats.get('total_words', 0)}")
    print(f"Average words per chunk: {stats.get('avg_words', 0):.1f}")
    print(f"Word count range: {stats.get('min_words', 0)} - {stats.get('max_words', 0)}")
    print(f"Sections covered: {stats.get('sections_covered', 0)}")
    print(f"\nLevel distribution: {stats.get('level_distribution', {})}")
    print(f"Type distribution: {stats.get('type_distribution', {})}")
    
    # Print sample chunks
    print("\n" + "=" * 70)
    print("SAMPLE CHUNKS")
    print("=" * 70)
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i + 1} ---")
        print(f"Section: {chunk['section_number']}")
        print(f"Title: {chunk['section_title'][:50]}...")
        print(f"Level: {chunk['level']}")
        print(f"Type: {chunk['chunk_type']}")
        print(f"Words: {chunk['word_count']}")
        print(f"Parents: {chunk['parent_chain']}")
        print(f"\nText preview:")
        print(chunk['text'][:400] + "...")
        print()