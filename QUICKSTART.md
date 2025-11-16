# MAHIKS-TR Quick Start Guide

## 🚀 Fast Setup (5 minutes)

### 1. Prerequisites Check
```bash
# Check Python version (need 3.11+)
python --version

# Check Docker
docker --version
docker-compose --version
```

### 2. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

**Required values in `.env`**:
- `OPENAI_API_KEY` - Your OpenAI API key
- `MYSQL_PASSWORD` - Choose a secure password
- `NEO4J_PASSWORD` - Choose a secure password

### 3. Start with Docker (Easiest)
```bash
# Start all services
docker-compose up -d

# Check if services are running
docker-compose ps

# View logs
docker-compose logs -f backend
```

### 4. Add Sample Documents
```bash
# Add your PDF/HTML/TXT files to:
# data/raw_documents/

# For testing, you can add any Turkish health document
```

### 5. Process Documents
```bash
# Run the knowledge base update
docker-compose exec backend python scripts/update_knowledge_base.py

# This will:
# - Extract text from documents
# - Create chunks
# - Build knowledge graph
# - Create vector embeddings
```

### 6. Test the API
```bash
# Check health
curl http://localhost:8000/health

# Ask a question
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SGK nedir?",
    "include_citations": true
  }'
```

### 7. Access Services
- **API Documentation**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474 (user: neo4j, password: from .env)
- **API Base URL**: http://localhost:8000

---

## 🔧 Local Development Setup (Without Docker)

### 1. Install Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt

# Download Turkish NLP model
python -m spacy download tr_core_news_lg
```

### 2. Setup Databases

**MySQL**:
```bash
# Install MySQL 8.0
# Start MySQL service
mysql -u root -p

# Create database
CREATE DATABASE mahiks_db;
exit
```

**Neo4j**:
```bash
# Download Neo4j Desktop or use Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:5.13
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with local database connections
```

### 4. Run Application
```bash
# Process documents
python scripts/update_knowledge_base.py

# Start API server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📝 Common Commands

### Docker Commands
```bash
# Stop all services
docker-compose down

# Restart a service
docker-compose restart backend

# View logs
docker-compose logs -f backend

# Execute command in container
docker-compose exec backend python scripts/update_knowledge_base.py

# Rebuild after code changes
docker-compose up -d --build
```

### Database Management
```bash
# Reset and rebuild knowledge base
docker-compose exec backend python scripts/update_knowledge_base.py --reset

# Check system status
curl http://localhost:8000/status

# View graph statistics
curl http://localhost:8000/api/graph/stats

# List all documents
curl http://localhost:8000/api/documents
```

---

## 🐛 Troubleshooting

### Services won't start
```bash
# Check if ports are already in use
lsof -i :8000  # Backend
lsof -i :3306  # MySQL
lsof -i :7474  # Neo4j HTTP
lsof -i :7687  # Neo4j Bolt

# Stop conflicting services or change ports in docker-compose.yml
```

### Database connection errors
```bash
# Wait for databases to fully start (30-60 seconds)
docker-compose logs mysql
docker-compose logs neo4j

# Restart services
docker-compose restart
```

### Out of memory
```bash
# Increase Docker memory limit in Docker Desktop settings
# Or reduce chunk size in .env:
CHUNK_SIZE=300
```

### Module not found errors
```bash
# Rebuild containers
docker-compose down
docker-compose up -d --build
```

---

## 📊 Testing Your Setup

### 1. Health Check
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","message":"All systems operational"}
```

### 2. System Status
```bash
curl http://localhost:8000/status | jq
# Should show document count, chunks, vectors, graph stats
```

### 3. Ask a Question
```bash
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Merhaba, sistemi test ediyorum",
    "include_citations": true
  }' | jq
```

### 4. Upload a Document
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@path/to/your/document.pdf"
```

---

## 🎯 Next Steps

1. **Add Real Documents**: Place Turkish health insurance documents in `data/raw_documents/`
2. **Process Documents**: Run the update script
3. **Test Queries**: Try asking questions about your documents
4. **Customize**: Adjust chunk size, top_k, and other settings in `.env`
5. **Monitor**: Check logs and database statistics
6. **Iterate**: Add more documents and refine the system

---

## 📚 Additional Resources

- [Full README](README.md)
- [API Documentation](http://localhost:8000/docs)
- [Project Definition](bitirme_rag/project_def.txt)
- [Architecture Guide](bitirme_rag/multi_agent_architecture.md)

---

**Need Help?** Check the main README.md or the troubleshooting section above.
