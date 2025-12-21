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
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_MAX_WORDS = 350      # Maximum words per chunk
DEFAULT_MIN_WORDS = 50       # Minimum words (lowered to keep small sections)
DEFAULT_MERGE_THRESHOLD = 40 # Sections smaller than this MAY be merged


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
    - Database storage
    
    Attributes:
        section_number: Section identifier like "1.4.1.A", "2.2.1.B-2"
        section_title: Human-readable title
        level: Hierarchy level (2=X.Y, 3=X.Y.Z, 4=X.Y.Z.A, 5=X.Y.Z.A-N)
        parent_chain: List of parent section numbers for context
        bolum: BÖLÜM name if detected (e.g., "BİRİNCİ BÖLÜM")
        fikra: Fıkra number if chunk is from specific paragraph
        chunk_type: How this chunk was created
        chunk_index: Index within split chunks (0, 1, 2...)
        is_merged: Whether this chunk contains merged sections
        merged_sections: List of section numbers if merged
    """
    section_number: str
    section_title: str
    level: int
    parent_chain: List[str] = field(default_factory=list)
    bolum: Optional[str] = None
    fikra: Optional[str] = None
    chunk_type: str = "full_section"
    chunk_index: int = 0
    is_merged: bool = False
    merged_sections: List[str] = field(default_factory=list)


@dataclass 
class Chunk:
    """
    Complete chunk with text and metadata.
    
    This is the main output of the chunker.
    
    Attributes:
        text: The actual chunk text (with context header if enabled)
        word_count: Number of words in the chunk
        order: Global order in document (0, 1, 2, ...)
        metadata: ChunkMetadata object with all details
    """
    text: str
    word_count: int
    order: int
    metadata: ChunkMetadata
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage or JSON serialization."""
        result = {
            'text': self.text,
            'word_count': self.word_count,
            'order': self.order,
            # Flatten metadata into the dict
            'section_number': self.metadata.section_number,
            'section_title': self.metadata.section_title,
            'level': self.metadata.level,
            'parent_chain': self.metadata.parent_chain,
            'bolum': self.metadata.bolum,
            'fikra': self.metadata.fikra,
            'chunk_type': self.metadata.chunk_type,
            'chunk_index': self.metadata.chunk_index,
            'is_merged': self.metadata.is_merged,
            'merged_sections': self.metadata.merged_sections,
        }
        return result


@dataclass
class RawSection:
    """
    Intermediate representation of a parsed section.
    Used internally before chunking.
    """
    section_number: str
    section_title: str
    content: str
    word_count: int
    level: int
    index: int
    is_merged: bool = False
    merged_sections: List[str] = field(default_factory=list)


@dataclass
class ChunkingStats:
    """Statistics about chunking results."""
    total_chunks: int
    total_words: int
    avg_words: float
    min_words: int
    max_words: int
    level_distribution: Dict[int, int]
    type_distribution: Dict[str, int]
    sections_covered: int
    
    def __str__(self) -> str:
        return f"""Chunking Statistics:
            Total chunks: {self.total_chunks}
            Total words: {self.total_words}
            Avg words/chunk: {self.avg_words:.1f}
            Word range: {self.min_words} - {self.max_words}
            Sections covered: {self.sections_covered}
            Level distribution: {self.level_distribution}
            Type distribution: {self.type_distribution}"""


# =============================================================================
# MAIN CHUNKER CLASS
# =============================================================================

class SUTChunker:
    """
    Structure-aware chunker for SUT documents - Version 2
    
    Key improvements over V1:
    - Small sections (1.2, 1.3, etc.) are NO LONGER LOST
    - Uses dataclasses for type safety
    - Better handling of header-only sections
    - Configurable preservation and merging
    
    Usage:
        chunker = SUTChunkerV2(max_words=350, preserve_all=True)
        chunks = chunker.chunk_document(text)
        
        for chunk in chunks:
            print(chunk.metadata.section_number)
            print(chunk.text)
            
        # Or convert to dicts for database
        chunk_dicts = [c.to_dict() for c in chunks]
    """
    
    # -------------------------------------------------------------------------
    # REGEX PATTERNS
    # -------------------------------------------------------------------------
    
    SECTION_PATTERN = re.compile(
        r'^[\s]*(\d+\.\d+(?:\.\d+)?(?:\.[A-ZÇĞİÖŞÜ])?(?:-\d+)?)\s*[-–]?\s*(.+?)$',
        re.MULTILINE
    )
    
    BOLUM_PATTERN = re.compile(
        r'(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU)\s+BÖLÜM',
        re.IGNORECASE
    )
    
    FIKRA_PATTERN = re.compile(r'^\s*\((\d+)\)\s+', re.MULTILINE)
    BENT_PATTERN = re.compile(r'^\s*([a-zçğıöşü])\)\s+', re.MULTILINE)
    EK_PATTERN = re.compile(r'EK[-\s]*(\d+(?:/[A-ZÇĞİÖŞÜ])?(?:-\d+)?)', re.IGNORECASE)
    
    # -------------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------------
    
    def __init__(
        self,
        max_words: int = DEFAULT_MAX_WORDS,
        min_words: int = DEFAULT_MIN_WORDS,
        merge_threshold: int = DEFAULT_MERGE_THRESHOLD,
        include_context: bool = True,
        context_max_length: int = 60,
        preserve_all: bool = True,
        merge_small: bool = True
    ):
        """
        Initialize the chunker.
        
        Args:
            max_words: Maximum words per chunk (350 for 512-token models)
            min_words: Minimum words to keep a chunk (lowered to 20)
            merge_threshold: Sections smaller than this MAY be merged
            include_context: Prepend parent section info to chunks
            context_max_length: Max characters per context line
            preserve_all: Keep ALL sections, even very small ones
            merge_small: Merge small sections with neighbors when sensible
        """
        self.max_words = max_words
        self.min_words = min_words
        self.merge_threshold = merge_threshold
        self.include_context = include_context
        self.context_max_length = context_max_length
        self.preserve_all = preserve_all
        self.merge_small = merge_small
        
        # Internal state (reset on each chunk_document call)
        self._section_titles: Dict[str, str] = {}
        self._current_bolum: Optional[str] = None
    
    # -------------------------------------------------------------------------
    # LEVEL DETECTION
    # -------------------------------------------------------------------------
    
    def detect_level(self, section_num: str) -> int:
        """
        Determine the hierarchy level of a section number.
        
        Returns:
            2 for X.Y (e.g., 1.1)
            3 for X.Y.Z (e.g., 1.4.1)
            4 for X.Y.Z.A (e.g., 1.4.1.A)
            5 for X.Y.Z.A-N (e.g., 1.5.1.A-1)
            0 for unknown format
        """
        if re.match(r'^\d+\.\d+\.\d+\.[A-ZÇĞİÖŞÜ]-\d+$', section_num):
            return 5
        elif re.match(r'^\d+\.\d+\.\d+\.[A-ZÇĞİÖŞÜ]$', section_num):
            return 4
        elif re.match(r'^\d+\.\d+\.\d+$', section_num):
            return 3
        elif re.match(r'^\d+\.\d+$', section_num):
            return 2
        return 0
    
    # -------------------------------------------------------------------------
    # PARENT CHAIN
    # -------------------------------------------------------------------------
    
    def get_parent_sections(self, section_num: str) -> List[str]:
        """
        Get all parent section numbers.
        
        Example: "1.5.1.A-1" → ["1.5", "1.5.1", "1.5.1.A"]
        """
        parents = []
        current = section_num
        
        while True:
            if re.match(r'^\d+\.\d+\.\d+\.[A-ZÇĞİÖŞÜ]-\d+$', current):
                current = re.sub(r'-\d+$', '', current)
                parents.append(current)
            elif re.match(r'^\d+\.\d+\.\d+\.[A-ZÇĞİÖŞÜ]$', current):
                current = re.sub(r'\.[A-ZÇĞİÖŞÜ]$', '', current)
                parents.append(current)
            elif re.match(r'^\d+\.\d+\.\d+$', current):
                current = '.'.join(current.split('.')[:-1])
                parents.append(current)
            else:
                break
        
        return list(reversed(parents))
    
    # -------------------------------------------------------------------------
    # CONTEXT BUILDING
    # -------------------------------------------------------------------------
    
    def build_context_header(
        self,
        section_num: str,
        section_title: str,
        fikra_num: Optional[str] = None
    ) -> str:
        """
        Build context header to prepend to chunks.
        
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
        
        # Add BÖLÜM
        if self._current_bolum:
            lines.append(f"[BÖLÜM: {self._current_bolum}]")
        
        # Add parent sections
        parents = self.get_parent_sections(section_num)
        for parent in parents:
            if parent in self._section_titles:
                title = self._section_titles[parent]
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
    
    def chunk_document(self, text: str) -> List[Chunk]:
        """
        Main method: Chunk entire SUT document.
        
        Args:
            text: Full document text
        
        Returns:
            List of Chunk objects
        """
        # Reset state
        self._section_titles = {}
        self._current_bolum = None
        
        # Find all section headers
        matches = list(self.SECTION_PATTERN.finditer(text))
        
        if not matches:
            # No sections found - return whole document
            metadata = ChunkMetadata(
                section_number="",
                section_title="Document",
                level=0
            )
            return [Chunk(
                text=text,
                word_count=len(text.split()),
                order=0,
                metadata=metadata
            )]
        
        # Build section title lookup
        for m in matches:
            section_num = m.group(1)
            title = m.group(2).strip()
            # Clean amendment notes
            title = re.sub(r'\(Değişik:.*?\)', '', title).strip()
            title = re.sub(r'\(Ek:.*?\)', '', title).strip()
            title = re.sub(r'\(Mülga:.*?\)', '', title).strip()
            self._section_titles[section_num] = title
        
        # Detect BÖLÜM
        bolum_match = self.BOLUM_PATTERN.search(text[:3000])
        if bolum_match:
            self._current_bolum = bolum_match.group(0)
        
        # STEP 1: Extract all raw sections
        raw_sections: List[RawSection] = []
        
        for i, match in enumerate(matches):
            section_num = match.group(1)
            section_title = self._section_titles.get(section_num, "")
            
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            
            raw_sections.append(RawSection(
                section_number=section_num,
                section_title=section_title,
                content=content,
                word_count=len(content.split()),
                level=self.detect_level(section_num),
                index=i
            ))
        
        # STEP 2: Merge small sections if enabled
        if self.merge_small:
            processed_sections = self._merge_small_sections(raw_sections)
        else:
            processed_sections = raw_sections
        
        # STEP 3: Create chunks from sections
        chunks: List[Chunk] = []
        
        for section in processed_sections:
            section_chunks = self._chunk_section(section)
            chunks.extend(section_chunks)
        
        # STEP 4: Filter and assign order
        final_chunks: List[Chunk] = []
        
        for chunk in chunks:
            if self.preserve_all or chunk.word_count >= self.min_words:
                chunk.order = len(final_chunks)
                final_chunks.append(chunk)
        
        return final_chunks
    
    # -------------------------------------------------------------------------
    # SECTION MERGING
    # -------------------------------------------------------------------------
    
    def _merge_small_sections(self, sections: List[RawSection]) -> List[RawSection]:
        """
        Merge small sections with neighbors.
        
        Strategy:
        - If a section has fewer words than merge_threshold
        - AND it's NOT a header-only section (parent of next section)
        - THEN merge it with the NEXT section
        - If it's the last section, merge with PREVIOUS
        
        This ensures sections like 1.2, 1.3 are NOT lost but combined
        with neighboring sections to form reasonable chunk sizes.
        """
        if not sections:
            return sections
        
        # First pass: identify which sections need merging
        needs_merge = []
        for i, section in enumerate(sections):
            is_small = section.word_count < self.merge_threshold
            
            # Check if this is a header-only section (parent of next)
            is_header = (
                i + 1 < len(sections) and
                self._is_parent_of(section.section_number, sections[i + 1].section_number)
            )
            
            # Small sections that are NOT headers should be merged
            needs_merge.append(is_small and not is_header)
        
        # Second pass: merge sections
        merged: List[RawSection] = []
        i = 0
        
        while i < len(sections):
            section = sections[i]
            
            # Check if this is a header-only section - skip it
            # (its title is preserved via parent_chain in children)
            is_header = (
                section.word_count < self.merge_threshold and
                i + 1 < len(sections) and
                self._is_parent_of(section.section_number, sections[i + 1].section_number)
            )
            
            if is_header:
                # Skip header sections - context preserved via parent_chain
                i += 1
                continue
            
            # Collect consecutive small sections to merge together
            sections_to_merge = [section]
            j = i + 1
            
            while j < len(sections):
                next_section = sections[j]
                
                # Check if next section is a header (parent of the one after it)
                next_is_header = (
                    next_section.word_count < self.merge_threshold and
                    j + 1 < len(sections) and
                    self._is_parent_of(next_section.section_number, sections[j + 1].section_number)
                )
                
                if next_is_header:
                    # Skip header, but stop merging chain here
                    break
                
                # Check if we should merge next section
                current_total = sum(s.word_count for s in sections_to_merge)
                
                # Merge if:
                # 1. Current section(s) are still small, OR
                # 2. Next section is small
                # AND combined size is reasonable
                should_merge = (
                    (current_total < self.merge_threshold or next_section.word_count < self.merge_threshold) and
                    current_total + next_section.word_count <= self.max_words
                )
                
                if should_merge:
                    sections_to_merge.append(next_section)
                    j += 1
                else:
                    break
            
            # Create merged section
            if len(sections_to_merge) == 1:
                # No merging needed
                merged.append(section)
            else:
                # Merge multiple sections
                merged_content = "\n\n".join(s.content for s in sections_to_merge)
                merged_section_numbers = [s.section_number for s in sections_to_merge]
                
                # Use first section's number and title as primary
                merged.append(RawSection(
                    section_number=sections_to_merge[0].section_number,
                    section_title=sections_to_merge[0].section_title,
                    content=merged_content,
                    word_count=len(merged_content.split()),
                    level=sections_to_merge[0].level,
                    index=sections_to_merge[0].index,
                    is_merged=True,
                    merged_sections=merged_section_numbers
                ))
            
            i = j  # Move to next unprocessed section
        
        return merged
    
    def _is_parent_of(self, parent_num: str, child_num: str) -> bool:
        """Check if parent_num is a parent of child_num."""
        return (child_num.startswith(parent_num + '.') or 
                child_num.startswith(parent_num + '-'))
    
    # -------------------------------------------------------------------------
    # SECTION CHUNKING
    # -------------------------------------------------------------------------
    
    def _chunk_section(self, section: RawSection) -> List[Chunk]:
        """Chunk a single section, splitting if necessary."""
        chunks: List[Chunk] = []
        
        context_header = self.build_context_header(
            section.section_number, 
            section.section_title
        )
        context_words = len(context_header.split()) if context_header else 0
        effective_max = self.max_words - context_words - 5
        
        # Section fits in one chunk
        if section.word_count <= effective_max:
            full_text = f"{context_header}\n\n{section.content}" if context_header else section.content
            
            metadata = ChunkMetadata(
                section_number=section.section_number,
                section_title=section.section_title,
                level=section.level,
                parent_chain=self.get_parent_sections(section.section_number),
                bolum=self._current_bolum,
                fikra=None,
                chunk_type='merged_section' if section.is_merged else 'full_section',
                chunk_index=0,
                is_merged=section.is_merged,
                merged_sections=section.merged_sections
            )
            
            chunks.append(Chunk(
                text=full_text,
                word_count=len(full_text.split()),
                order=0,  # Will be set later
                metadata=metadata
            ))
            return chunks
        
        # Section too large - try splitting by fıkra
        fikra_matches = list(self.FIKRA_PATTERN.finditer(section.content))
        
        if fikra_matches:
            for j, fm in enumerate(fikra_matches):
                fikra_start = fm.start()
                fikra_end = fikra_matches[j + 1].start() if j + 1 < len(fikra_matches) else len(section.content)
                fikra_content = section.content[fikra_start:fikra_end].strip()
                fikra_num = fm.group(1)
                
                fikra_chunks = self._chunk_fikra(
                    section, fikra_content, fikra_num
                )
                chunks.extend(fikra_chunks)
        else:
            # No fıkralar - split by sentences
            sentence_chunks = self._split_by_sentences(
                section, section.content, None, context_header
            )
            chunks.extend(sentence_chunks)
        
        return chunks
    
    def _chunk_fikra(
        self, 
        section: RawSection, 
        fikra_content: str, 
        fikra_num: str
    ) -> List[Chunk]:
        """Chunk a single fıkra."""
        chunks: List[Chunk] = []
        
        fikra_context = self.build_context_header(
            section.section_number, 
            section.section_title, 
            fikra_num
        )
        context_words = len(fikra_context.split()) if fikra_context else 0
        effective_max = self.max_words - context_words - 5
        
        fikra_words = len(fikra_content.split())
        
        if fikra_words <= effective_max:
            full_text = f"{fikra_context}\n\n{fikra_content}" if fikra_context else fikra_content
            
            metadata = ChunkMetadata(
                section_number=section.section_number,
                section_title=section.section_title,
                level=section.level,
                parent_chain=self.get_parent_sections(section.section_number),
                bolum=self._current_bolum,
                fikra=fikra_num,
                chunk_type='fikra',
                chunk_index=0
            )
            
            chunks.append(Chunk(
                text=full_text,
                word_count=len(full_text.split()),
                order=0,
                metadata=metadata
            ))
        else:
            # Fıkra too large - split by sentences
            sentence_chunks = self._split_by_sentences(
                section, fikra_content, fikra_num, fikra_context
            )
            chunks.extend(sentence_chunks)
        
        return chunks
    
    def _split_by_sentences(
        self,
        section: RawSection,
        text: str,
        fikra_num: Optional[str],
        context_header: str
    ) -> List[Chunk]:
        """Split text at sentence boundaries."""
        chunks: List[Chunk] = []
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        context_words = len(context_header.split()) if context_header else 0
        effective_max = self.max_words - context_words - 5
        
        current_sentences: List[str] = []
        current_words = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_words = len(sentence.split())
            
            if current_words + sentence_words > effective_max and current_sentences:
                # Save current chunk
                chunk_text = ' '.join(current_sentences)
                full_text = f"{context_header}\n\n{chunk_text}" if context_header else chunk_text
                
                metadata = ChunkMetadata(
                    section_number=section.section_number,
                    section_title=section.section_title,
                    level=section.level,
                    parent_chain=self.get_parent_sections(section.section_number),
                    bolum=self._current_bolum,
                    fikra=fikra_num,
                    chunk_type='sentence_split',
                    chunk_index=chunk_index
                )
                
                chunks.append(Chunk(
                    text=full_text,
                    word_count=len(full_text.split()),
                    order=0,
                    metadata=metadata
                ))
                
                current_sentences = []
                current_words = 0
                chunk_index += 1
            
            current_sentences.append(sentence)
            current_words += sentence_words
        
        # Last chunk
        if current_sentences:
            chunk_text = ' '.join(current_sentences)
            full_text = f"{context_header}\n\n{chunk_text}" if context_header else chunk_text
            
            metadata = ChunkMetadata(
                section_number=section.section_number,
                section_title=section.section_title,
                level=section.level,
                parent_chain=self.get_parent_sections(section.section_number),
                bolum=self._current_bolum,
                fikra=fikra_num,
                chunk_type='sentence_split',
                chunk_index=chunk_index
            )
            
            chunks.append(Chunk(
                text=full_text,
                word_count=len(full_text.split()),
                order=0,
                metadata=metadata
            ))
        
        return chunks
    
    # -------------------------------------------------------------------------
    # STATISTICS
    # -------------------------------------------------------------------------
    
    def get_statistics(self, chunks: List[Chunk]) -> ChunkingStats:
        """Get statistics about chunking results."""
        if not chunks:
            return ChunkingStats(
                total_chunks=0,
                total_words=0,
                avg_words=0,
                min_words=0,
                max_words=0,
                level_distribution={},
                type_distribution={},
                sections_covered=0
            )
        
        word_counts = [c.word_count for c in chunks]
        levels = [c.metadata.level for c in chunks]
        chunk_types = [c.metadata.chunk_type for c in chunks]
        
        return ChunkingStats(
            total_chunks=len(chunks),
            total_words=sum(word_counts),
            avg_words=sum(word_counts) / len(word_counts),
            min_words=min(word_counts),
            max_words=max(word_counts),
            level_distribution={l: levels.count(l) for l in sorted(set(levels))},
            type_distribution={t: chunk_types.count(t) for t in set(chunk_types)},
            sections_covered=len(set(c.metadata.section_number for c in chunks))
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def chunk_sut_document(
    text: str,
    max_words: int = 350,
    min_words: int = 50,
    preserve_all: bool = True,
    merge_small: bool = True,
    as_dicts: bool = False
) -> List:
    """
    Convenience function to chunk a SUT document.
    
    Args:
        text: Full document text
        max_words: Maximum words per chunk
        preserve_all: Keep all sections, even small ones
        merge_small: Merge small sections with neighbors
        as_dicts: If True, return List[Dict] instead of List[Chunk]
    
    Returns:
        List of Chunk objects (or dicts if as_dicts=True)
    """
    chunker = SUTChunker(
        max_words=max_words,
        min_words=min_words,
        preserve_all=preserve_all,
        merge_small=merge_small
    )
    
    chunks = chunker.chunk_document(text)
    
    if as_dicts:
        return [c.to_dict() for c in chunks]
    
    return chunks


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Sample test
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
    
    # Create chunker
    chunker = SUTChunker(
        max_words=350,
        min_words=50,        # Very low to capture 1.2, 1.3
        preserve_all=True,
        merge_small=True    
    )



    chunks = chunker.chunk_document(text)
    
    # Print statistics
    stats = chunker.get_statistics(chunks)
    
    print("=" * 70)
    print("CHUNKING STATISTICS")
    print("=" * 70)
    print(f"Total chunks: {stats.total_chunks}")
    print(f"Total words: {stats.total_words}")
    print(f"Average words per chunk: {stats.avg_words:.1f}")
    print(f"Word count range: {stats.min_words} - {stats.max_words}")
    print(f"Sections covered: {stats.sections_covered}")
    print(f"\nLevel distribution: {stats.level_distribution}")
    print(f"Type distribution: {stats.type_distribution}")
    
    # Print sample chunks
    print("\n" + "=" * 70)
    print("SAMPLE CHUNKS")
    print("=" * 70)
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i + 1} ---")
        print(f"Section: {chunk.metadata.section_number}")
        print(f"Title: {chunk.metadata.section_title[:50]}...")
        print(f"Level: {chunk.metadata.level}")
        print(f"Type: {chunk.metadata.chunk_type}")
        print(f"Words: {chunk.word_count}")
        print(f"Parents: {chunk.metadata.parent_chain}")
        print(f"\nText preview:")
        print(chunk.text)
        print()

    with open("output.txt", "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            f.write(f"\n--- Chunk {i + 1} ---\n")
            f.write(f"Section: {chunk.metadata.section_number}\n")
            f.write(f"Title: {chunk.metadata.section_title[:50]}...\n")
            f.write(f"Level: {chunk.metadata.level}\n")
            f.write(f"Type: {chunk.metadata.chunk_type}\n")
            f.write(f"Words: {chunk.word_count}\n")
            f.write(f"Parents: {chunk.metadata.parent_chain}\n")
            f.write(f"\nText preview:\n")
            f.write(chunk.text + "\n\n\n")
        
        



