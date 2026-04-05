"""
Configuration for MAHIKS-TR Backend
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration"""

    # MySQL Configuration
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "mahiks_db")

    # Neo4j Configuration
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    # ChromaDB Configuration
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "medical_chunks")

    # Ollama Configuration (Local LLM)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # Embedding Model Configuration
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    # Application Settings
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Text Processing Settings
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

    # SUT Chunker Settings
    SUT_MAX_WORDS = int(os.getenv("SUT_MAX_WORDS", "350"))
    SUT_MIN_WORDS = int(os.getenv("SUT_MIN_WORDS", "100"))
    SUT_MERGE_THRESHOLD = int(os.getenv("SUT_MERGE_THRESHOLD", "75"))

    # Retrieval Settings
    VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "5"))
    GRAPH_MAX_DEPTH = int(os.getenv("GRAPH_MAX_DEPTH", "2"))

    # Data Directory to processde the docs for the chunking and embedding creation
    DATA_DIR = os.getenv("DATA_DIR", "./data/raw_documents")

    # BM25 Configuration (Lexical Search)
    BM25_PERSIST_DIR = os.getenv("BM25_PERSIST_DIR", "./bm25_data")
    BM25_K1 = float(os.getenv("BM25_K1", "1.5"))  # Term frequency saturation
    BM25_B = float(os.getenv("BM25_B", "0.75"))   # Length normalization
    BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "0.3"))  # Fusion weight for hybrid search

    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


    # Redis Cache Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_DB = int(os.getenv('REDIS_DB', '0'))
    CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
    CACHE_TTL = int(os.getenv('CACHE_TTL', '3600'))  # 1 hour default

    # KG Extraction Configuration
    KG_EXTRACTION_METHOD = os.getenv("KG_EXTRACTION_METHOD", "local")  # "local", "gemini", "auto"
    KG_OLLAMA_MODEL = os.getenv("KG_OLLAMA_MODEL", "qwen2.5:7b")
    KG_CHUNK_SIZE = int(os.getenv("KG_CHUNK_SIZE", "3000"))

    # CORS Configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # Conversation Settings
    CONVERSATION_HISTORY_LIMIT = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "6"))
    MAX_GENERATION_TOKENS = int(os.getenv("MAX_GENERATION_TOKENS", "2000"))

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            ("MYSQL_PASSWORD", cls.MYSQL_PASSWORD),
            ("NEO4J_PASSWORD", cls.NEO4J_PASSWORD),
            ("JWT_SECRET", cls.JWT_SECRET)
        ]

        missing = [name for name, value in required if not value]

        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}\n"
                f"Please check your .env file"
            )

    @classmethod
    def get_mysql_uri(cls):
        """Get MySQL connection URI"""
        return f"mysql+pymysql://{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DATABASE}"
