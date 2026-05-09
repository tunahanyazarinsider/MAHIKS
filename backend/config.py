"""
Configuration for MAHIKS-TR Backend
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""

    # ── Databases ─────────────────────────────────────────────────────────────

    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "mahiks_db")

    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
    QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "sut_documents")
    QDRANT_DENSE_VECTOR_NAME = os.getenv("QDRANT_DENSE_VECTOR_NAME", "dense")
    QDRANT_SPARSE_VECTOR_NAME = os.getenv("QDRANT_SPARSE_VECTOR_NAME", "sparse_bm25")
    QDRANT_SPARSE_MODEL = os.getenv("QDRANT_SPARSE_MODEL", "Qdrant/bm25")
    QDRANT_SPARSE_LANGUAGE = os.getenv("QDRANT_SPARSE_LANGUAGE", "turkish")
    QDRANT_DENSE_DIM = int(os.getenv("QDRANT_DENSE_DIM", "1024"))

    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))

    # ── Embedding ─────────────────────────────────────────────────────────────

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    # ── Generation LLM ────────────────────────────────────────────────────────
    # LLM_PROVIDER selects the answer-generation backend.
    # Options: ollama (default) | openai | openrouter | gemini | vertex

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_LLM_MODEL = os.getenv("OPENROUTER_LLM_MODEL", "qwen/qwen-2.5-72b-instruct")
    OPENROUTER_REFERER = os.getenv("OPENROUTER_REFERER")
    OPENROUTER_TITLE = os.getenv("OPENROUTER_TITLE", "MAHIKS-TR")

    # GEMINI_API_KEY is preferred; GOOGLE_API_KEY is accepted as fallback by GeminiClient
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")

    # ── Knowledge Graph Extraction ────────────────────────────────────────────
    # KG_EXTRACTION_METHOD can differ from LLM_PROVIDER.
    # Options: ollama (default) | gemini | vertex | openrouter

    KG_EXTRACTION_METHOD = os.getenv("KG_EXTRACTION_METHOD", "ollama")
    KG_CHUNK_SIZE = int(os.getenv("KG_CHUNK_SIZE", "3000"))

    KG_OLLAMA_MODEL = os.getenv("KG_OLLAMA_MODEL", "qwen2.5:7b")
    KG_VERTEX_MODEL = os.getenv("KG_VERTEX_MODEL", "gemini-2.5-flash")
    KG_OPENROUTER_MODEL = os.getenv("KG_OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")
    KG_GEMINI_MODEL = os.getenv("KG_GEMINI_MODEL")  # Defaults to GEMINI_MODEL if not set; no separate KG_GEMINI_MODEL
    # Gemini KG uses GEMINI_API_KEY and GEMINI_MODEL by default (no separate KG_GEMINI_MODEL)

    # ── Judge Model (evaluation) ──────────────────────────────────────────────

    JUDGE_MODEL_PROVIDER = os.getenv("JUDGE_MODEL_PROVIDER", "ollama")
    JUDGE_MODEL_OLLAMA = os.getenv("JUDGE_MODEL_OLLAMA", "qwen2.5:7b")
    JUDGE_MODEL_GEMINI = os.getenv("JUDGE_MODEL_GEMINI", "gemini-2.5-flash")
    JUDGE_MODEL_VERTEX = os.getenv("JUDGE_MODEL_VERTEX", "gemini-2.5-flash")
    JUDGE_MODEL_OPENROUTER = os.getenv("JUDGE_MODEL_OPENROUTER", "qwen/qwen-2.5-72b-instruct")

    # ── Authentication ────────────────────────────────────────────────────────

    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # ── Application ───────────────────────────────────────────────────────────

    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # ── Text Processing ───────────────────────────────────────────────────────

    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

    SUT_MAX_WORDS = int(os.getenv("SUT_MAX_WORDS", "350"))
    SUT_MIN_WORDS = int(os.getenv("SUT_MIN_WORDS", "100"))
    SUT_MERGE_THRESHOLD = int(os.getenv("SUT_MERGE_THRESHOLD", "75"))

    # ── Retrieval ─────────────────────────────────────────────────────────────

    VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "5"))
    GRAPH_MAX_DEPTH = int(os.getenv("GRAPH_MAX_DEPTH", "2"))

    # ── Conversation & Generation ─────────────────────────────────────────────

    CONVERSATION_HISTORY_LIMIT = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "6"))
    MAX_GENERATION_TOKENS = int(os.getenv("MAX_GENERATION_TOKENS", "2000"))

    # ── Data ──────────────────────────────────────────────────────────────────

    DATA_DIR = os.getenv("DATA_DIR", "./data/raw_documents")

    # ── Methods ───────────────────────────────────────────────────────────────

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            ("MYSQL_PASSWORD", cls.MYSQL_PASSWORD),
            ("NEO4J_PASSWORD", cls.NEO4J_PASSWORD),
            ("JWT_SECRET", cls.JWT_SECRET),
        ]
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}\n"
                f"Please check your .env file"
            )

    @classmethod
    def get_mysql_uri(cls):
        return (
            f"mysql+pymysql://{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}"
            f"@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DATABASE}"
        )
