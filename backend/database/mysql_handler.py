"""
MySQL Database Handler for MAHIKS-TR
Manages documents and text chunks storage
"""
import mysql.connector
from mysql.connector import Error
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import json


class MySQLHandler:
    """Handler for MySQL database operations"""

    def __init__(self, host: str, user: str, password: str, database: str):
        """
        Initialize MySQL connection

        Args:
            host: MySQL server host
            user: MySQL username
            password: MySQL password
            database: Database name
        """
        try:
            self.connection = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                charset='utf8mb4',
                use_unicode=True
            )
            self.cursor = self.connection.cursor(dictionary=True)
            print(f"✓ Connected to MySQL database: {database}")
        except Error as e:
            print(f"✗ Error connecting to MySQL: {e}")
            raise

    def create_tables(self):
        """Create necessary database tables if they don't exist"""
        try:
            # Create users table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    display_name VARCHAR(255),
                    role VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Create documents table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_url VARCHAR(1024),
                    source_name VARCHAR(255) NOT NULL,
                    document_type VARCHAR(50),
                    content_hash VARCHAR(64) NOT NULL,
                    processed_at DATETIME,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_content_hash (content_hash),
                    INDEX idx_document_type (document_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Create chunks table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    document_id INT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    chunk_order INT NOT NULL,
                    metadata_json JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    INDEX idx_document_id (document_id),
                    INDEX idx_chunk_order (chunk_order)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Create user queries table for logging
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_queries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    answer_text TEXT,
                    response_time_ms INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            self.connection.commit()
            print("✓ Database tables created successfully")
        except Error as e:
            print(f"✗ Error creating tables: {e}")
            raise

    def insert_document(self, source_url: str, source_name: str,
                       doc_type: str, content: str) -> int:
        """
        Insert a new document into the database

        Args:
            source_url: Path or URL of the source document
            source_name: Human-readable name
            doc_type: Type of document (e.g., 'SUT', 'PDF', 'HTML')
            content: Full text content for hashing

        Returns:
            Document ID
        """
        try:
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

            # Check if document already exists
            self.cursor.execute(
                "SELECT id FROM documents WHERE content_hash = %s",
                (content_hash,)
            )
            existing = self.cursor.fetchone()

            if existing:
                print(f"  Document already exists (ID: {existing['id']}), skipping...")
                return existing['id']

            query = """
                INSERT INTO documents
                (source_url, source_name, document_type, content_hash, processed_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            self.cursor.execute(
                query,
                (source_url, source_name, doc_type, content_hash, datetime.now())
            )
            self.connection.commit()

            doc_id = self.cursor.lastrowid
            print(f"  ✓ Document inserted with ID: {doc_id}")
            return doc_id
        except Error as e:
            print(f"✗ Error inserting document: {e}")
            raise

    def insert_chunk(self, document_id: int, chunk_text: str,
                    chunk_order: int, metadata: Optional[Dict] = None) -> int:
        """
        Insert a text chunk into the database

        Args:
            document_id: ID of the parent document
            chunk_text: The text content of the chunk
            chunk_order: Sequential order of the chunk
            metadata: Optional metadata (page number, section, etc.)

        Returns:
            Chunk ID
        """
        try:
            metadata_json = json.dumps(metadata) if metadata else None

            query = """
                INSERT INTO chunks
                (document_id, chunk_text, chunk_order, metadata_json)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(
                query,
                (document_id, chunk_text, chunk_order, metadata_json)
            )
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"✗ Error inserting chunk: {e}")
            raise

    def get_chunks_by_ids(self, chunk_ids: List[int]) -> List[Dict]:
        """
        Retrieve chunks by their IDs

        Args:
            chunk_ids: List of chunk IDs

        Returns:
            List of chunk dictionaries
        """
        if not chunk_ids:
            return []

        try:
            placeholders = ','.join(['%s'] * len(chunk_ids))
            query = f"""
                SELECT c.*, d.source_name, d.document_type
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.id IN ({placeholders})
                ORDER BY FIELD(c.id, {placeholders})
            """
            self.cursor.execute(query, chunk_ids + chunk_ids)
            return self.cursor.fetchall()
        except Error as e:
            print(f"✗ Error retrieving chunks: {e}")
            return []

    def get_all_chunks_for_document(self, document_id: int) -> List[Dict]:
        """
        Get all chunks for a specific document

        Args:
            document_id: Document ID

        Returns:
            List of chunks ordered by chunk_order
        """
        try:
            query = """
                SELECT * FROM chunks
                WHERE document_id = %s
                ORDER BY chunk_order
            """
            self.cursor.execute(query, (document_id,))
            return self.cursor.fetchall()
        except Error as e:
            print(f"✗ Error retrieving document chunks: {e}")
            return []

    def log_query(self, query_text: str, answer_text: str,
                  response_time_ms: int):
        """
        Log a user query for analytics

        Args:
            query_text: User's question
            answer_text: Generated answer
            response_time_ms: Response time in milliseconds
        """
        try:
            query = """
                INSERT INTO user_queries
                (query_text, answer_text, response_time_ms)
                VALUES (%s, %s, %s)
            """
            self.cursor.execute(query, (query_text, answer_text, response_time_ms))
            self.connection.commit()
        except Error as e:
            print(f"✗ Error logging query: {e}")

    def get_document_count(self) -> int:
        """Get total number of documents"""
        self.cursor.execute("SELECT COUNT(*) as count FROM documents")
        return self.cursor.fetchone()['count']

    def get_chunk_count(self) -> int:
        """Get total number of chunks"""
        self.cursor.execute("SELECT COUNT(*) as count FROM chunks")
        return self.cursor.fetchone()['count']

    def close(self):
        """Close database connection"""
        if self.connection.is_connected():
            self.cursor.close()
            self.connection.close()
            print("✓ MySQL connection closed")
