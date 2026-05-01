"""
Vector backend factory.
Returns ChromaDBHandler or QdrantHandler based on Config.VECTOR_BACKEND.
"""
from backend.config import Config


def build_vector_handler():
    backend = (Config.VECTOR_BACKEND or "chroma").lower()
    if backend == "qdrant":
        from backend.database.qdrant_handler import QdrantHandler
        print(f"→ Vector backend: Qdrant ({Config.QDRANT_URL}, "
              f"collection={Config.QDRANT_COLLECTION_NAME})")
        return QdrantHandler(
            url=Config.QDRANT_URL,
            api_key=Config.QDRANT_API_KEY,
            collection_name=Config.QDRANT_COLLECTION_NAME,
            embedding_model_name=Config.EMBEDDING_MODEL,
            dense_vector_name=Config.QDRANT_DENSE_VECTOR_NAME,
            sparse_vector_name=Config.QDRANT_SPARSE_VECTOR_NAME,
            sparse_model_name=Config.QDRANT_SPARSE_MODEL,
            sparse_language=Config.QDRANT_SPARSE_LANGUAGE,
            dense_dim=Config.QDRANT_DENSE_DIM,
        )

    if backend != "chroma":
        print(f"⚠ Unknown VECTOR_BACKEND='{backend}', falling back to chroma")

    from backend.database.chroma_handler import ChromaDBHandler
    print(f"→ Vector backend: ChromaDB ({Config.CHROMA_PERSIST_DIR}, "
          f"collection={Config.CHROMA_COLLECTION_NAME})")
    return ChromaDBHandler(
        persist_directory=Config.CHROMA_PERSIST_DIR,
        collection_name=Config.CHROMA_COLLECTION_NAME,
        embedding_model_name=Config.EMBEDDING_MODEL,
    )


def is_hybrid_backend() -> bool:
    return (Config.VECTOR_BACKEND or "chroma").lower() == "qdrant"
