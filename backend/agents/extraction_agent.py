"""
Extraction Agent for MAHIKS-TR
Responsible for extracting text from various document formats and chunking
"""
import PyPDF2
from bs4 import BeautifulSoup
from typing import List, Dict
import re


class ExtractionAgent:
    """Agent for text extraction and chunking"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Initialize the extraction agent

        Args:
            chunk_size: Number of words per chunk
            chunk_overlap: Number of overlapping words between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        print(f"✓ Extraction agent initialized (chunk_size={chunk_size}, overlap={chunk_overlap})")

    def extract_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        Extract text from PDF file

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of page dictionaries with text content
        """
        print(f"  Extracting text from PDF: {pdf_path}")
        text_content = []

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)

                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():  # Only add non-empty pages
                        text_content.append({
                            'page': page_num + 1,
                            'text': text.strip()
                        })

                print(f"    ✓ Extracted {len(text_content)} pages from {total_pages} total pages")
        except Exception as e:
            print(f"    ✗ Error extracting PDF: {e}")
            raise

        return text_content

    def extract_from_html(self, html_path: str) -> str:
        """
        Extract text from HTML file

        Args:
            html_path: Path to HTML file

        Returns:
            Cleaned text content
        """
        print(f"  Extracting text from HTML: {html_path}")

        try:
            with open(html_path, 'r', encoding='utf-8') as file:
                soup = BeautifulSoup(file, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                # Get text
                text = soup.get_text(separator=' ')

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)

                print(f"    ✓ Extracted {len(text)} characters")
                return text

        except Exception as e:
            print(f"    ✗ Error extracting HTML: {e}")
            raise

    def extract_from_txt(self, txt_path: str) -> str:
        """
        Extract text from plain text file

        Args:
            txt_path: Path to text file

        Returns:
            Text content
        """
        print(f"  Extracting text from TXT: {txt_path}")

        try:
            with open(txt_path, 'r', encoding='utf-8') as file:
                text = file.read()
                print(f"    ✓ Extracted {len(text)} characters")
                return text
        except Exception as e:
            print(f"    ✗ Error extracting TXT: {e}")
            raise

    def extract_text(self, file_path: str, file_type: str = None) -> str:
        """
        Extract text from any supported file format

        Args:
            file_path: Path to the file
            file_type: File type (PDF, HTML, TXT) - auto-detected if None

        Returns:
            Extracted text
        """
        if file_type is None:
            file_type = file_path.split('.')[-1].upper()

        if file_type == 'PDF':
            pages = self.extract_from_pdf(file_path)
            return '\n\n'.join([p['text'] for p in pages])
        elif file_type in ['HTML', 'HTM']:
            return self.extract_from_html(file_path)
        elif file_type in ['TXT', 'MD']:
            return self.extract_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove special characters but keep Turkish characters
        # Keep: letters, numbers, basic punctuation, Turkish characters
        text = re.sub(r'[^\w\s.,!?;:()\-–—\"\'ğüşıöçĞÜŞİÖÇ]', '', text)

        return text.strip()

    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Split text into overlapping chunks

        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to each chunk

        Returns:
            List of chunk dictionaries
        """
        # Clean the text first
        text = self.clean_text(text)

        # Split into words
        words = text.split()
        chunks = []

        if len(words) == 0:
            return chunks

        # Create overlapping chunks
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)

            chunk_dict = {
                'text': chunk_text,
                'order': len(chunks),
                'word_count': len(chunk_words)
            }

            # Add metadata if provided
            if metadata:
                chunk_dict['metadata'] = metadata

            chunks.append(chunk_dict)

            # Stop if we've reached the end
            if i + self.chunk_size >= len(words):
                break

        print(f"    ✓ Created {len(chunks)} chunks from {len(words)} words")
        return chunks

    def chunk_by_sentences(self, text: str, sentences_per_chunk: int = 5) -> List[str]:
        """
        Alternative chunking strategy: chunk by sentences

        Args:
            text: Text to chunk
            sentences_per_chunk: Number of sentences per chunk

        Returns:
            List of text chunks
        """
        # Simple sentence splitting (can be improved with spaCy)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        for i in range(0, len(sentences), sentences_per_chunk):
            chunk = '. '.join(sentences[i:i + sentences_per_chunk])
            if chunk:
                chunks.append(chunk + '.')

        return chunks

    def extract_and_chunk(self, file_path: str, file_type: str = None,
                         document_metadata: Dict = None) -> List[Dict]:
        """
        Complete pipeline: extract text and create chunks

        Args:
            file_path: Path to document
            file_type: Document type
            document_metadata: Metadata about the document

        Returns:
            List of chunk dictionaries ready for database insertion
        """
        # Extract text
        text = self.extract_text(file_path, file_type)

        # Create chunks
        chunks = self.chunk_text(text, metadata=document_metadata)

        return chunks
