# MAHIKS-TR: Multi-Agent Health Insurance Knowledge System

A RAG system combining vector search, BM25 lexical search, and knowledge graphs to answer Turkish health insurance questions using local LLMs.

## Architecture

```
Query → Vector Search (BGE-M3 / ChromaDB) ─┐
                                             ├→ RRF Fusion → Sub-chunk → Cross-Encoder Rerank → Top 10
        BM25 Search (TurkishStemmer)       ─┘                (~120 words)   (mmarco-mMiniLMv2)
                                                                                    │
                                                                              Qwen 2.5 (7B)
                                                                              via Ollama
                                                                                    │
                                                                                 Answer
```

### Pipeline

| Step | Component | Detail |
|------|-----------|--------|
| Embedding | BAAI/bge-m3 | 1024d multilingual vectors |
| Vector DB | ChromaDB | Cosine similarity search |
| Lexical Search | BM25 | Turkish stemming, k1=1.5, b=0.75 |
| Fusion | RRF | Reciprocal Rank Fusion, k=60 |
| Sub-chunking | Custom | 500w chunks → 120w overlapping sub-chunks |
| Reranking | mmarco-mMiniLMv2-L12-H384-v1 | Cross-encoder scoring with threshold filtering |
| LLM | Qwen 2.5 7B (Q4) | Local via Ollama, ~42 tok/s on M4 Pro |
| Knowledge Graph | Neo4j | Entity-relationship triplets (optional) |
| Cache | Redis | Query + embedding cache with LRU eviction |

### Tech Stack

**Backend**: FastAPI, Python 3.11, sentence-transformers, spaCy (tr_core_news_lg)
**Frontend**: React 18, TypeScript, Vite, Tailwind CSS v4, Radix UI, react-markdown
**Databases**: MySQL 8.0, ChromaDB, Neo4j 5.13, Redis 7
**LLM**: Ollama (runs on host, not in Docker)

## Quick Start

### Prerequisites

- Docker Desktop (32GB+ memory recommended)
- Ollama (`brew install ollama`)
- macOS with Apple Silicon (M1/M2/M3/M4)

### Setup

```bash
# 1. Clone and configure
cd MAHIKS
cp .env.example .env
# Edit .env: set MYSQL_PASSWORD, NEO4J_PASSWORD, JWT_SECRET

# 2. Generate JWT secret
openssl rand -hex 32  # paste into .env JWT_SECRET=

# 3. Install and start Ollama
brew install ollama
brew services start ollama

# 4. Pull models
ollama pull qwen2.5:7b    # Generation (4.7 GB)
ollama pull qwen2.5:14b   # Optional: higher quality generation (9 GB)

# 5. Start all services
docker compose up -d

# 6. Process documents (first time only)
# Place PDFs in data/raw_documents/ then:
docker compose run --rm backend python -m scripts.vectorize_only

# 7. Access
# Frontend: http://localhost:3000
# API:      http://localhost:8000
# API Docs: http://localhost:8000/docs
# Neo4j:    http://localhost:7474
```

### Docker Memory

Set Docker Desktop memory to **32GB** (Settings > Resources > Memory). The BGE-M3 embedding model (~2.3GB) + cross-encoder + PyTorch need significant memory.

## Project Structure

```
MAHIKS/
├── backend/
│   ├── agents/
│   │   ├── orchestrator_agent.py      # Query pipeline coordinator
│   │   ├── retrieval_agent.py         # Hybrid retrieval + sub-chunk reranking
│   │   ├── generation_agent_ollama.py # LLM generation via /api/chat
│   │   ├── local_kg_extractor.py      # Knowledge graph extraction
│   │   ├── vectorization_agent.py     # Embedding generation
│   │   ├── extraction_agent.py        # PDF/HTML text extraction
│   │   ├── ingestion_agent.py         # Document discovery
│   │   └── query_preprocessor.py      # Query normalization
│   ├── database/
│   │   ├── mysql_handler.py           # Document & chunk storage
│   │   ├── chroma_handler.py          # Vector DB (BGE-M3)
│   │   ├── neo4j_handler.py           # Knowledge graph
│   │   ├── bm25_handler.py            # Lexical search index
│   │   └── cache_handler.py           # Redis cache
│   ├── main.py                        # FastAPI app + endpoints
│   └── config.py                      # Configuration
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ChatScreen.tsx         # Main chat interface
│       │   ├── ChatMessage.tsx        # Message bubbles + markdown + citations
│       │   ├── ChatHistory.tsx        # Conversation sidebar
│       │   ├── RagInfoScreen.tsx      # RAG pipeline debugger
│       │   ├── LoginScreen.tsx        # Authentication
│       │   └── SignUpScreen.tsx       # Registration
│       ├── api/                       # API clients (axios + SSE streaming)
│       └── styles/globals.css         # Theme (DM Sans + Source Serif 4)
├── scripts/
│   ├── update_knowledge_base.py       # Full pipeline (chunks + KG)
│   └── vectorize_only.py             # Chunks only (no KG)
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## API Endpoints

### Query
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ask` | POST | Single query with answer + citations |
| `/api/ask/stream` | POST | Streaming response (SSE) |
| `/api/batch-ask` | POST | Batch queries (max 10) |
| `/api/rag/debug` | POST | RAG pipeline debugger (no LLM, returns sub-chunks + scores) |

### Documents & Knowledge Graph
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload document |
| `/api/documents` | GET | List documents |
| `/api/graph/stats` | GET | Graph statistics |
| `/api/graph/entity/{name}` | GET | Entity relationships |

### Conversations
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/conversations` | GET/POST | List/create conversations |
| `/api/conversations/{id}` | GET/PATCH/DELETE | Manage conversation |
| `/api/conversations/{id}/messages` | GET/POST | Messages |

### System
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/status` | GET | System status |
| `/api/cache/stats` | GET | Cache statistics |
| `/api/cache/clear` | POST | Clear cache |

## Configuration

Key environment variables (`.env`):

```bash
# LLM
OLLAMA_MODEL=qwen2.5:7b          # Generation model
KG_OLLAMA_MODEL=qwen2.5:7b       # KG extraction model
EMBEDDING_MODEL=BAAI/bge-m3      # Embedding model (change = re-index)

# Auth
JWT_SECRET=<openssl rand -hex 32>
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Retrieval
CHUNK_SIZE=500                    # Words per chunk
CHUNK_OVERLAP=50                  # Overlap words
VECTOR_TOP_K=5                    # Vector search results

# Generation
MAX_GENERATION_TOKENS=2000
CONVERSATION_HISTORY_LIMIT=6
```

## Frontend Features

- Streaming chat with markdown rendering (react-markdown + remark-gfm)
- Collapsible citation panel with source names + relevance scores
- Welcome screen with suggestion chips
- Conversation management (create, rename, delete)
- RAG Pipeline Debugger (interactive sub-chunk inspection)
- Responsive design (sidebar hidden on mobile)
- Medical-themed UI (DM Sans + Source Serif 4, emerald green palette)

## Retrieval Pipeline Detail

```
1. Vector Search (BGE-M3 → ChromaDB)     → 10 results
2. BM25 Search (TurkishStemmer)           → 10 results
3. Reciprocal Rank Fusion (k=60)          → Top 10 merged
4. Sub-chunking (120 words, 30 overlap)   → ~60 sub-chunks
5. Cross-Encoder Reranking                → Score each sub-chunk
6. Threshold Filter (CE ≥ 0.1)            → Remove irrelevant
7. Top 10 sub-chunks (~1200 words)        → Send to LLM
```

This two-stage approach uses large chunks (500 words) for better recall during vector search, then splits into small sub-chunks (120 words) for precise reranking. The result is focused, relevant context sent to the LLM.

## Development

```bash
# Frontend dev (hot reload)
cd frontend && npm run dev

# Backend logs
docker compose logs -f backend

# Rebuild after code changes
docker compose up -d --build backend
docker compose build --no-cache frontend && docker compose up -d frontend
```

---

Built for Turkish healthcare knowledge management. Sabanci University FENS.
