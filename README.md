# MAHIKS-TR: Multi-Agent Health Insurance Knowledge System for Turkish Healthcare

A sophisticated multi-agent system that integrates advanced Retrieval-Augmented Generation (RAG) techniques with dynamic medical knowledge graphs to automatically extract, organize, and reason over Turkish health insurance sources.

## 🎯 Project Overview

MAHIKS-TR addresses the complex challenge of intelligent health insurance knowledge management in the Turkish healthcare system. The system uses:

- **Hybrid RAG Architecture**: Combines vector search (ChromaDB) with knowledge graph reasoning (Neo4j)
- **Multi-Agent System**: Specialized agents for ingestion, extraction, knowledge graph building, vectorization, retrieval, and generation
- **Turkish Language Support**: Full support for Turkish medical and insurance terminology
- **Multi-Database Architecture**: MySQL for documents, ChromaDB for embeddings, Neo4j for knowledge graphs
- **100% Local & Private**: Uses Ollama for LLM, SentenceTransformers for embeddings - no external API calls!

## 🏗️ Architecture

### Offline Processing Pipeline
1. **Ingestion Agent**: Discovers and monitors source documents
2. **Extraction Agent**: Extracts and chunks text from PDFs, HTML, and TXT files
3. **Knowledge Graph Agent**: Builds triplets (Subject-Predicate-Object) using NLP
4. **Vectorization Agent**: Creates embeddings and stores in ChromaDB

### Online Query Pipeline
1. **Query Orchestrator**: Coordinates the entire workflow
2. **Retrieval Agent**: Performs hybrid search (vector + graph)
3. **Generation Agent**: Uses LLM to generate answers with citations

## 📁 Project Structure

```
MAHIKS/
├── backend/
│   ├── agents/
│   │   ├── ingestion_agent.py
│   │   ├── extraction_agent.py
│   │   ├── kg_agent.py
│   │   ├── vectorization_agent.py
│   │   ├── retrieval_agent.py
│   │   ├── generation_agent.py
│   │   └── orchestrator_agent.py
│   ├── database/
│   │   ├── mysql_handler.py
│   │   ├── chroma_handler.py
│   │   └── neo4j_handler.py
│   ├── models/
│   │   └── schemas.py
│   ├── main.py
│   └── config.py
├── scripts/
│   └── update_knowledge_base.py
├── data/
│   └── raw_documents/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env
```

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose (recommended)
- **Ollama** installed on your Mac (runs on host, not in Docker)
- Or, for local setup:
  - Python 3.11+
  - MySQL 8.0+
  - Neo4j 5.13+
  - Ollama (for local LLM)

### Installation

#### Option 1: Using Docker with Host Ollama (Recommended for Low Memory)

**Why Host Ollama?** Running Ollama in Docker can consume excessive memory. By running it on your Mac, you save ~3-4 GB RAM and get better performance.

**🚀 Quick Start:**

```bash
# Step 1: Install Ollama on your Mac (if not already installed)
brew install ollama
# Or download from: https://ollama.com/download

# Step 2: Start Ollama on your Mac
ollama serve

# Step 3: Pull a small, fast model (in a new terminal)
ollama pull llama3.2:1b
# OR for better quality: ollama pull qwen2.5:0.5b

# Step 4: Use the automated startup script
./start_demo.sh
```

The `start_demo.sh` script automatically:
- Checks if Ollama is running on your Mac
- Verifies the model is installed
- Starts Docker services (MySQL, Neo4j, Backend only)
- Tests connectivity
- Shows you system status

**Manual Setup:**

1. **Start Ollama on your Mac:**
```bash
# Terminal 1: Start Ollama (keep running)
ollama serve

# Terminal 2: Pull a model
ollama pull llama3.2:1b
```

2. **Setup project:**
```bash
cd MAHIKS
cp .env.example .env
```

3. **Edit `.env` file** with your credentials:
```bash
MYSQL_PASSWORD=your_secure_password
NEO4J_PASSWORD=your_neo4j_password
OLLAMA_MODEL=llama3.2:1b  # or qwen2.5:0.5b
```

4. **Start Docker services** (Ollama runs on host, not in Docker):
```bash
docker-compose up -d
```

**Note:** The docker-compose.yml is configured to use `host.docker.internal:11434` to connect to your Mac's Ollama instance.

See [HOST_OLLAMA_SETUP.md](docs/HOST_OLLAMA_SETUP.md) for detailed explanation and troubleshooting.

5. **Add documents** to `data/raw_documents/`
   - Supported: PDF, HTML, TXT files
   - Just placing files here is NOT enough!

6. **Process documents into RAG** (CRITICAL STEP):
```bash
docker exec -it mahiks-backend python scripts/update_knowledge_base.py
```

This script:
- Extracts text from your documents
- Generates embeddings (local, no API)
- Builds knowledge graph
- Stores everything in databases

7. **Access the system**:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

**📖 Detailed Guides:**
- See `RAG_SETUP_GUIDE.md` for complete RAG setup instructions
- See `OLLAMA_SETUP.md` for Ollama configuration and models

#### Option 2: Local Installation

1. **Install dependencies**:
```bash
pip install -r requirements.txt
python -m spacy download tr_core_news_lg
```

2. **Setup databases**:
```bash
# Start MySQL
mysql -u root -p
CREATE DATABASE mahiks_db;

# Start Neo4j
# Download from neo4j.com and start
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Run the application**:
```bash
# Update knowledge base first
python scripts/update_knowledge_base.py

# Start the API server
uvicorn backend.main:app --reload
```

## 📚 Usage

### Adding Documents

Place your Turkish health insurance documents in `data/raw_documents/`:
- Supported formats: PDF, HTML, TXT, MD
- Examples: SUT documents, SGK regulations, insurance policies

### Updating Knowledge Base

```bash
# Process all documents
python scripts/update_knowledge_base.py

# Reset and rebuild everything
python scripts/update_knowledge_base.py --reset

# Use custom data directory
python scripts/update_knowledge_base.py --data-dir /path/to/documents
```

### Making Queries

#### Using the API

```bash
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SGK hangi ilaçları karşılar?",
    "include_citations": true,
    "top_k": 5
  }'
```

#### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/ask",
    json={
        "question": "Diyabet tedavisi için SGK kapsamı nedir?",
        "include_citations": True
    }
)

result = response.json()
print(result['answer'])
print(result['citations'])
```

### API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /status` - System status and statistics
- `POST /api/ask` - Ask a question
- `POST /api/batch-ask` - Batch query processing
- `POST /api/upload` - Upload a document
- `GET /api/documents` - List all documents
- `GET /api/graph/stats` - Knowledge graph statistics
- `GET /api/graph/entity/{name}` - Get entity information

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MYSQL_HOST` | MySQL server host | `localhost` |
| `MYSQL_PASSWORD` | MySQL password | - |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_PASSWORD` | Neo4j password | - |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `llama2` |
| `CHUNK_SIZE` | Characters per chunk | `500` |
| `CHUNK_OVERLAP` | Overlapping characters | `50` |
| `VECTOR_TOP_K` | Results to retrieve | `5` |

## 🧪 Testing

```bash
# Run tests
pytest

# Run specific test
pytest tests/test_retrieval.py

# With coverage
pytest --cov=backend tests/
```

## 📊 Monitoring

### Database Statistics

```bash
# Check system status
curl http://localhost:8000/status

# View knowledge graph stats
curl http://localhost:8000/api/graph/stats
```

### Logs

```bash
# View backend logs
docker-compose logs -f backend

# View all service logs
docker-compose logs -f
```

## 🛠️ Development

### Project Components

1. **Database Handlers**: Abstract database operations
2. **Agents**: Specialized components for specific tasks
3. **API**: FastAPI-based REST API
4. **Scripts**: Maintenance and update utilities

### Adding a New Agent

1. Create agent file in `backend/agents/`
2. Implement agent class with required methods
3. Register agent in orchestrator or main.py
4. Update documentation

## 🐛 Troubleshooting

### Common Issues

**Database connection errors**:
```bash
# Check if services are running
docker-compose ps

# Restart services
docker-compose restart
```

**Memory issues with large documents**:
- Increase Docker memory limit
- Reduce `CHUNK_SIZE` in .env
- Process documents in smaller batches

**spaCy model not found**:
```bash
python -m spacy download tr_core_news_lg
```

## 📖 Documentation

- [Project Definition](bitirme_rag/project_def.txt)
- [Architecture Details](bitirme_rag/multi_agent_architecture.md)
- [Database Schema](bitirme_rag/mysql_schema_and_workflow.md)
- [API Documentation](http://localhost:8000/docs) (when running)

## 🤝 Contributing

This is an academic project for FENS. Contributions are welcome!

## 📄 License

This project is developed as part of an academic assignment.

## 🙏 Acknowledgments

- Turkish healthcare data from SGK
- spaCy for Turkish NLP
- Ollama for local LLM inference
- SentenceTransformers for multilingual embeddings
- Neo4j, ChromaDB, and MySQL communities

## 📧 Contact

For questions and support, please refer to the project documentation or create an issue.

---

**Built with ❤️ for Turkish Healthcare**
