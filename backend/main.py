"""
MAHIKS-TR Backend API
Main FastAPI application
"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from pathlib import Path

from backend.config import Config
from backend.models.schemas import (
    QueryRequest, QueryResponse, HealthResponse, StatusResponse,
    DocumentUploadResponse, BatchQueryRequest, BatchQueryResponse
)

# Database handlers
from backend.database.mysql_handler import MySQLHandler
from backend.database.chroma_handler import ChromaDBHandler
from backend.database.neo4j_handler import Neo4jHandler
from backend.database.bm25_handler import BM25Handler
from backend.database.cache_handler import (
    init_cache_handler,
    get_cache_handler
)

# Agents
from backend.agents.retrieval_agent import RetrievalAgent
from backend.agents.generation_agent import GenerationAgent
from backend.agents.generation_agent_ollama import GenerationAgentOllama
from backend.agents.orchestrator_agent import QueryOrchestratorAgent

# Routers
from backend.controller.UserController.UserController import user_router

from backend.core.error_handlers import register_exception_handlers

# Global variables for handlers
mysql_handler = None
chroma_handler = None
neo4j_handler = None
bm25_handler = None
orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup and shutdown)"""
    global mysql_handler, chroma_handler, neo4j_handler, orchestrator

    print("\n" + "="*70)
    print("MAHIKS-TR Backend Starting...")
    print("="*70)

    # Validate configuration
    try:
        Config.validate()
        print("✓ Configuration validated")
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        raise

    # Initialize database handlers
    try:
        print("\nInitializing databases...")

        mysql_handler = MySQLHandler(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE
        )
        mysql_handler.create_tables()

        chroma_handler = ChromaDBHandler(
            persist_directory=Config.CHROMA_PERSIST_DIR,
            collection_name=Config.CHROMA_COLLECTION_NAME
        )

        neo4j_handler = Neo4jHandler(
            uri=Config.NEO4J_URI,
            user=Config.NEO4J_USER,
            password=Config.NEO4J_PASSWORD
        )
        neo4j_handler.create_indexes()

        # Initialize BM25 Handler
        bm25_handler = BM25Handler(
            persist_directory=Config.BM25_PERSIST_DIR,
            k1=Config.BM25_K1,
            b=Config.BM25_B
        )

        # Initialize Redis Cache
        # if redis setup fails, continue without cache functionality
        if Config.CACHE_ENABLED:
            try:
                init_cache_handler(
                    host=Config.REDIS_HOST,
                    port=Config.REDIS_PORT
                )
                print(f"✓ Redis cache initialized at {Config.REDIS_HOST}:{Config.REDIS_PORT}")
            except Exception as e:
                print(f"⚠️  Redis cache failed to initialize: {e}")
                print("   Continuing without cache...")
        else:
            print("ℹ️  Cache disabled (CACHE_ENABLED=false)")

        print("✓ All databases initialized")

    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        raise

    # Initialize agents
    try:
        print("\nInitializing agents...")

        retrieval_agent = RetrievalAgent(
            chroma_handler,
            neo4j_handler,
            mysql_handler,
            bm25_handler
        )

        # Use Ollama for local LLM generation
        generation_agent = GenerationAgentOllama(
            base_url=Config.OLLAMA_BASE_URL,
            model=Config.OLLAMA_MODEL
        )

        orchestrator = QueryOrchestratorAgent(
            retrieval_agent,
            generation_agent
        )

        print("✓ All agents initialized")

    except Exception as e:
        print(f"✗ Agent initialization failed: {e}")
        raise

    print("\n" + "="*70)
    print("✓ MAHIKS-TR Backend Ready")
    print("="*70 + "\n")

    yield

    # Shutdown
    print("\nShutting down MAHIKS-TR Backend...")
    if bm25_handler:
        bm25_handler.save_index()
    if mysql_handler:
        mysql_handler.close()
    if neo4j_handler:
        neo4j_handler.close()
    print("✓ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="MAHIKS-TR API",
    description="Multi-Agent Health Insurance Knowledge System for Turkish Healthcare",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include user router
app.include_router(user_router)

# Register exception handlers
register_exception_handlers(app)

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint"""
    return {
        "status": "running",
        "message": "MAHIKS-TR API is running. Visit /docs for API documentation."
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "All systems operational"
    }

@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    cache = get_cache_handler()
    if not cache:
        raise HTTPException(status_code=503, detail="Cache not available")

    return cache.get_stats()


@app.post("/api/cache/clear")
async def clear_cache(cache_type: str = "all"):
    """
    Clear cache.

    Args:
        cache_type: 'all' (default) or 'queries'
    """
    cache = get_cache_handler()
    if not cache:
        raise HTTPException(status_code=503, detail="Cache not available")

    if cache_type == "all":
        cache.invalidate_all()
    elif cache_type == "queries":
        cache.invalidate_queries()
    else:
        raise HTTPException(status_code=400, detail="Invalid cache_type. Use 'all' or 'queries'")

    return {"message": f"Cache '{cache_type}' cleared successfully"}


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get system status and statistics"""
    try:
        status = orchestrator.get_pipeline_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    """
    Ask a question and get an AI-generated answer

    This endpoint performs:
    1. Hybrid retrieval (vector + graph search)
    2. Answer generation using LLM
    3. Source citation
    """
    try:
        result = orchestrator.process_query(
            request.question,
            include_citations=request.include_citations
        )

        # Log query to database
        mysql_handler.log_query(
            query_text=request.question,
            answer_text=result['answer'],
            response_time_ms=result['metadata']['response_time_ms']
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@app.post("/api/batch-ask", response_model=BatchQueryResponse)
async def batch_ask(request: BatchQueryRequest):
    """Process multiple queries in batch"""
    try:
        results = orchestrator.process_batch_queries(request.queries)

        successful = sum(1 for r in results if 'error' not in r)
        failed = len(results) - successful

        return {
            "results": results,
            "total_queries": len(results),
            "successful": successful,
            "failed": failed
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing batch queries: {str(e)}"
        )


@app.post("/api/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document for processing
    (Note: This requires the offline processing agents to be imported)
    """
    try:
        # Save uploaded file
        data_dir = Path(Config.DATA_DIR)
        data_dir.mkdir(parents=True, exist_ok=True)

        file_path = data_dir / file.filename

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "success": True,
            "message": f"File '{file.filename}' uploaded successfully. "
                      f"Run the knowledge base update script to process it.",
            "document_id": None,
            "chunks_created": 0,
            "triplets_extracted": 0
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading document: {str(e)}"
        )


@app.get("/api/documents")
async def list_documents():
    """List all documents in the knowledge base"""
    try:
        mysql_handler.cursor.execute("""
            SELECT id, source_name, document_type, processed_at, created_at
            FROM documents
            ORDER BY created_at DESC
        """)
        documents = mysql_handler.cursor.fetchall()

        return {
            "total": len(documents),
            "documents": documents
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing documents: {str(e)}"
        )


@app.get("/api/graph/stats")
async def get_graph_stats():
    """Get knowledge graph statistics"""
    try:
        stats = neo4j_handler.get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting graph stats: {str(e)}"
        )


@app.get("/api/graph/entity/{entity_name}")
async def get_entity_info(entity_name: str):
    """Get information about a specific entity in the knowledge graph"""
    try:
        info = neo4j_handler.get_entity_info(entity_name)
        if info is None:
            raise HTTPException(
                status_code=404,
                detail=f"Entity '{entity_name}' not found"
            )
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting entity info: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=Config.APP_HOST,
        port=Config.APP_PORT,
        reload=Config.DEBUG
    )
