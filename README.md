# MAHIKS-TR: Multi-Agent Health Insurance Knowledge System

A RAG system combining hybrid dense + sparse vector search and knowledge graphs to answer Turkish health insurance questions using local LLMs.

## Architecture

```
Query → Qdrant Hybrid Search ─┐
        ┌─ Dense (BGE-M3 1024d cosine)        │
        └─ Sparse BM25 (FastEmbed Qdrant/bm25, Turkish, IDF)
        Server-side RRF Fusion ──→ Sub-chunk → Cross-Encoder Rerank → Top 10
                                    (~120 words)   (mmarco-mMiniLMv2)
                                                            │
                                                      Qwen 2.5 (7B)
                                                      via Ollama
                                                            │
                                                         Answer
```

### Pipeline

| Step | Component | Detail |
|------|-----------|--------|
| Dense Embedding | BAAI/bge-m3 | 1024d multilingual vectors |
| Sparse Embedding | FastEmbed `Qdrant/bm25` | Turkish Snowball stemmer, IDF modifier |
| Vector DB | Qdrant | Two named vectors per point (`dense`, `sparse_bm25`) |
| Fusion | Qdrant RRF | Reciprocal Rank Fusion, server-side, k=60 |
| Sub-chunking | Custom | 500w chunks → 120w overlapping sub-chunks |
| Reranking | mmarco-mMiniLMv2-L12-H384-v1 | Cross-encoder scoring with threshold filtering |
| LLM | Qwen 2.5 7B (Q4) | Local via Ollama, ~42 tok/s on M4 Pro |
| Knowledge Graph | Neo4j | Entity-relationship triplets (optional) |
| Cache | Redis | Query + embedding cache with LRU eviction |

### Tech Stack

**Backend**: FastAPI, Python 3.11, sentence-transformers, spaCy (tr_core_news_lg)
**Frontend**: React 18, TypeScript, Vite, Tailwind CSS v4, Radix UI, react-markdown
**Databases**: MySQL 8.0, Qdrant 1.12, Neo4j 5.13, Redis 7
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
│   │   ├── qdrant_handler.py          # Hybrid vector DB (dense BGE-M3 + sparse BM25)
│   │   ├── neo4j_handler.py           # Knowledge graph
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
│   ├── vectorize_only.py              # Chunks only (no KG)
│   ├── generate_eval_questions.py     # Generate Q&A pairs (multi-provider LLM)
│   └── evaluate_api.py               # API-based evaluation (IR metrics + LLM judge + latency)
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
1. Qdrant Hybrid Search                   → Top 10 (server-side RRF)
   ├─ Dense: BGE-M3 1024d cosine
   └─ Sparse: FastEmbed Qdrant/bm25 (Turkish, IDF)
2. Sub-chunking (120 words, 30 overlap)   → ~60 sub-chunks
3. Cross-Encoder Reranking                → Score each sub-chunk
4. Threshold Filter (CE_SCORE_THRESHOLD)  → Remove irrelevant
5. Top 10 sub-chunks (~1200 words)        → Send to LLM
```

This two-stage approach uses large chunks (500 words) for better recall during vector search, then splits into small sub-chunks (120 words) for precise reranking. The result is focused, relevant context sent to the LLM.

## Evaluation

Evaluation runs entirely inside Docker — no local Python setup needed.

### Step 1 — Generate Evaluation Questions

Samples random indexed chunks and uses an LLM to write a Turkish question + ground truth answer pair for each. Supports multiple providers for higher quality output.

```bash
# Default: OpenRouter (qwen/qwen-2.5-72b-instruct) — best quality/cost ratio
docker compose run --rm backend python -m scripts.generate_eval_questions --count 20

# OpenAI
docker compose run --rm backend python -m scripts.generate_eval_questions --provider openai --model gpt-4o --count 20

# Gemini
docker compose run --rm backend python -m scripts.generate_eval_questions --provider gemini --model gemini-2.5-flash --count 20

# Anthropic
docker compose run --rm backend python -m scripts.generate_eval_questions --provider anthropic --model claude-haiku-4-5-20251001 --count 20

# Local Ollama (free, lower quality)
docker compose run --rm backend python -m scripts.generate_eval_questions --provider ollama --count 20

# Custom output path
docker compose run --rm backend python -m scripts.generate_eval_questions --count 20 --output data/my_questions.json
```

Output is saved to `data/eval_questions.json`. Review the questions before running evaluation — bad ground truth corrupts your metrics.

**Provider selection tip:** For eval datasets that will be reused, prefer a strong model (GPT-4o, Gemini 2.5 Flash) — you only generate once and evaluate many times.

### Step 2 — Run Evaluation

Calls the live backend API to evaluate retrieval and generation quality, then uses an external LLM as judge. Reports IR metrics, generation quality scores, and latency statistics.

```bash
# Default: OpenRouter judge (qwen/qwen-2.5-72b-instruct)
docker compose run --rm backend python -m scripts.evaluate_api

# OpenAI judge
docker compose run --rm backend python -m scripts.evaluate_api --judge-provider openai --judge-model gpt-4o-mini

# Gemini judge
docker compose run --rm backend python -m scripts.evaluate_api --judge-provider gemini --judge-model gemini-2.5-flash

# Anthropic judge
docker compose run --rm backend python -m scripts.evaluate_api --judge-provider anthropic --judge-model claude-haiku-4-5-20251001

# Local Ollama judge (no API cost)
docker compose run --rm backend python -m scripts.evaluate_api --judge-provider ollama

# Quick test run (first 5 questions only)
docker compose run --rm backend python -m scripts.evaluate_api --limit 5

# Retrieval metrics only — skip LLM judge
docker compose run --rm backend python -m scripts.evaluate_api --skip-generation

# Custom questions file or output path
docker compose run --rm backend python -m scripts.evaluate_api --questions data/my_questions.json --output data/my_report.json
```

**Retrieval metrics** (2 stages compared side-by-side):

| Stage | What it measures |
|---|---|
| Stage 1 — Vector | Qdrant hybrid search ranking (dense BGE-M3 + sparse BM25, RRF fused) |
| Stage 2 — Full pipeline | After cross-encoder sub-chunk reranking |

Metrics per stage: `Hit@1`, `Hit@3`, `Hit@5`, `Hit@10`, `MRR`, `MAP`, `nDCG@5`, `nDCG@10`

**Generation metrics** (LLM-as-judge, scored 1–5):

| Metric | Description |
|---|---|
| Faithfulness | Every claim in the answer is grounded in retrieved context |
| Answer Relevance | The answer directly and completely addresses the question |
| Context Precision | Retrieved sub-chunks were actually useful for the answer |
| Context Recall | Ground-truth facts are covered by retrieved context *(requires ground_truth)* |

**Latency statistics** (both retrieval and generation): `mean`, `median`, `p95`, `p99`, `min`, `max`

Report is saved as JSON to `data/eval_api_report_<timestamp>.json`.

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
