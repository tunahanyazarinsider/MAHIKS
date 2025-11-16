"""
Ingestion Agent for MAHIKS-TR
Responsible for discovering and collecting source documents
"""
import os
from pathlib import Path
from typing import List, Dict
import requests
from datetime import datetime


class IngestionAgent:
    """Agent for document ingestion and monitoring"""

    def __init__(self, data_directory: str = "./data/raw_documents"):
        """
        Initialize the ingestion agent

        Args:
            data_directory: Directory to scan for documents
        """
        self.data_directory = Path(data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        print(f"✓ Ingestion agent initialized (directory: {self.data_directory})")

    def scan_documents(self) -> List[Dict]:
        """
        Scan the data directory for supported document formats

        Returns:
            List of document metadata dictionaries
        """
        supported_formats = ['.pdf', '.txt', '.html', '.htm', '.md']
        documents = []

        print(f"\nScanning directory: {self.data_directory}")

        for file_path in self.data_directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in supported_formats:
                documents.append({
                    'path': str(file_path),
                    'name': file_path.stem,
                    'type': file_path.suffix[1:].upper(),
                    'size': file_path.stat().st_size,
                    'modified': datetime.fromtimestamp(file_path.stat().st_mtime)
                })

        print(f"Found {len(documents)} documents")
        return documents

    def download_document(self, url: str, save_name: str) -> str:
        """
        Download a document from a URL

        Args:
            url: URL to download from
            save_name: Filename to save as

        Returns:
            Path to saved file
        """
        try:
            print(f"Downloading: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            save_path = self.data_directory / save_name

            with open(save_path, 'wb') as f:
                f.write(response.content)

            print(f"  ✓ Saved to: {save_path}")
            return str(save_path)

        except Exception as e:
            print(f"  ✗ Error downloading {url}: {e}")
            raise

    def download_sgk_documents(self) -> List[str]:
        """
        Download documents from SGK website
        (This is a placeholder - actual URLs need to be added)

        Returns:
            List of downloaded file paths
        """
        # Example SGK document URLs (these are placeholders)
        sgk_sources = [
            # {
            #     'url': 'https://www.sgk.gov.tr/...',
            #     'name': 'SUT_2024.pdf'
            # },
        ]

        downloaded_files = []
        for source in sgk_sources:
            try:
                file_path = self.download_document(source['url'], source['name'])
                downloaded_files.append(file_path)
            except Exception as e:
                print(f"  Warning: Failed to download {source['name']}: {e}")

        return downloaded_files

    def monitor_for_updates(self, known_hashes: Dict[str, str]) -> List[Dict]:
        """
        Check for new or updated documents

        Args:
            known_hashes: Dictionary mapping file paths to their content hashes

        Returns:
            List of new or updated documents
        """
        import hashlib

        current_documents = self.scan_documents()
        updated_documents = []

        for doc in current_documents:
            # Calculate current hash
            with open(doc['path'], 'rb') as f:
                content = f.read()
                current_hash = hashlib.sha256(content).hexdigest()

            # Check if new or updated
            if doc['path'] not in known_hashes or known_hashes[doc['path']] != current_hash:
                doc['content_hash'] = current_hash
                updated_documents.append(doc)

        return updated_documents

    def get_document_metadata(self, file_path: str) -> Dict:
        """
        Get metadata for a specific document

        Args:
            file_path: Path to the document

        Returns:
            Metadata dictionary
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        return {
            'path': str(path),
            'name': path.stem,
            'type': path.suffix[1:].upper(),
            'size': path.stat().st_size,
            'modified': datetime.fromtimestamp(path.stat().st_mtime),
            'absolute_path': str(path.absolute())
        }
