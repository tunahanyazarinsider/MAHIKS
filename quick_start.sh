#!/bin/bash

# MAHIKS-TR Quick Start Script
# This script helps you set up the entire RAG system quickly

set -e  # Exit on any error

echo "=========================================="
echo "MAHIKS-TR Quick Start"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check if docker-compose is available
echo -e "${YELLOW}[1/6] Checking Docker...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose not found. Please install Docker and Docker Compose.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"
echo ""

# Step 2: Start services
echo -e "${YELLOW}[2/6] Starting Docker services...${NC}"
docker-compose up -d
echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Step 3: Wait for services to be healthy
echo -e "${YELLOW}[3/6] Waiting for services to be healthy (this may take 30-60 seconds)...${NC}"
sleep 10

# Check each service
services=("mahiks-mysql" "mahiks-neo4j" "mahiks-ollama")
for service in "${services[@]}"; do
    echo "  Checking $service..."
    timeout=60
    elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if docker inspect --format='{{.State.Health.Status}}' $service 2>/dev/null | grep -q "healthy"; then
            echo -e "  ${GREEN}✓ $service is healthy${NC}"
            break
        fi
        sleep 5
        elapsed=$((elapsed + 5))
    done

    if [ $elapsed -ge $timeout ]; then
        echo -e "  ${YELLOW}⚠ $service is taking longer than expected${NC}"
    fi
done
echo ""

# Step 4: Pull Ollama model
echo -e "${YELLOW}[4/6] Pulling Ollama model...${NC}"
echo "  Which model would you like to use?"
echo "  1) llama2 (recommended for testing - fastest)"
echo "  2) mistral (good Turkish support)"
echo "  3) llama3 (best quality, requires more resources)"
echo ""
read -p "  Enter choice [1-3] (default: 1): " model_choice

case $model_choice in
    2)
        MODEL="mistral"
        ;;
    3)
        MODEL="llama3"
        ;;
    *)
        MODEL="llama2"
        ;;
esac

echo "  Pulling $MODEL model (this may take a few minutes on first run)..."
docker exec -it mahiks-ollama ollama pull $MODEL

# Update .env if it exists
if [ -f .env ]; then
    if grep -q "OLLAMA_MODEL" .env; then
        sed -i.bak "s/OLLAMA_MODEL=.*/OLLAMA_MODEL=$MODEL/" .env
        echo -e "${GREEN}✓ Updated .env with OLLAMA_MODEL=$MODEL${NC}"
    else
        echo "OLLAMA_MODEL=$MODEL" >> .env
        echo -e "${GREEN}✓ Added OLLAMA_MODEL=$MODEL to .env${NC}"
    fi
fi
echo ""

# Step 5: Check for documents
echo -e "${YELLOW}[5/6] Checking for documents...${NC}"
if [ ! -d "data/raw_documents" ]; then
    echo "  Creating data/raw_documents directory..."
    mkdir -p data/raw_documents
fi

doc_count=$(find data/raw_documents -type f \( -name "*.pdf" -o -name "*.html" -o -name "*.txt" \) 2>/dev/null | wc -l)

if [ "$doc_count" -eq 0 ]; then
    echo -e "${YELLOW}⚠ No documents found in data/raw_documents/${NC}"
    echo ""
    echo "  Please add your PDF, HTML, or TXT files to:"
    echo "  $(pwd)/data/raw_documents/"
    echo ""
    read -p "  Press Enter when you've added your documents, or 's' to skip... " skip_docs

    if [ "$skip_docs" = "s" ]; then
        echo -e "${YELLOW}  Skipping document processing${NC}"
        SKIP_PROCESSING=true
    else
        doc_count=$(find data/raw_documents -type f \( -name "*.pdf" -o -name "*.html" -o -name "*.txt" \) 2>/dev/null | wc -l)
    fi
fi

if [ "$doc_count" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $doc_count document(s)${NC}"
fi
echo ""

# Step 6: Process documents
if [ "$SKIP_PROCESSING" != "true" ] && [ "$doc_count" -gt 0 ]; then
    echo -e "${YELLOW}[6/6] Processing documents into RAG system...${NC}"
    echo "  This will:"
    echo "  - Extract text from documents"
    echo "  - Generate embeddings (local, no API needed)"
    echo "  - Build knowledge graph"
    echo ""

    docker exec -it mahiks-backend python scripts/update_knowledge_base.py

    echo -e "${GREEN}✓ Document processing complete${NC}"
else
    echo -e "${YELLOW}[6/6] Skipping document processing${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Your MAHIKS-TR RAG system is running:"
echo ""
echo "  🌐 API:           http://localhost:8000"
echo "  📚 API Docs:      http://localhost:8000/docs"
echo "  🔍 Neo4j Browser: http://localhost:7474"
echo "  🗄️  MySQL:        localhost:3306"
echo "  🤖 Ollama:        localhost:11434"
echo ""
echo "Next steps:"
echo ""
if [ "$doc_count" -eq 0 ]; then
    echo "  1. Add documents to data/raw_documents/"
    echo "  2. Process them: docker exec -it mahiks-backend python scripts/update_knowledge_base.py"
    echo "  3. Try asking questions!"
else
    echo "  1. Try asking a question:"
    echo ""
    echo "     curl -X POST http://localhost:8000/api/ask \\"
    echo "       -H 'Content-Type: application/json' \\"
    echo "       -d '{\"question\": \"Sağlık sigortası nedir?\", \"include_citations\": true}'"
    echo ""
fi
echo "  View logs:    docker-compose logs -f"
echo "  Stop system:  docker-compose down"
echo ""
echo "For more help, see:"
echo "  - RAG_SETUP_GUIDE.md (detailed RAG setup)"
echo "  - OLLAMA_SETUP.md (Ollama configuration)"
echo ""
echo "=========================================="
