#!/bin/bash

# MAHIKS-TR Demo Startup Script
# This script helps you start the system for your course demo

echo "========================================================================"
echo "MAHIKS-TR Demo Startup"
echo "========================================================================"
echo ""

# Step 1: Check if Ollama is running on host
echo "Step 1: Checking Ollama on host Mac..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama is running on host"
    echo ""
    echo "Available models:"
    ollama list
else
    echo "❌ Ollama is NOT running on host!"
    echo ""
    echo "Please start Ollama first:"
    echo "  Terminal 1: ollama serve"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo ""
echo "========================================================================"

# Step 2: Check which model to use
echo "Step 2: Checking model configuration..."
if [ -f .env ]; then
    MODEL=$(grep OLLAMA_MODEL .env | cut -d'=' -f2)
    if [ -z "$MODEL" ]; then
        MODEL="llama3.2:1b"
    fi
else
    MODEL="llama3.2:1b"
fi

echo "Configured model: $MODEL"

# Check if model exists
if ollama list | grep -q "$MODEL"; then
    echo "✅ Model '$MODEL' is installed"
else
    echo "⚠️  Model '$MODEL' is NOT installed"
    echo ""
    echo "Do you want to pull it now? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "Pulling model $MODEL..."
        ollama pull "$MODEL"
    else
        echo "Skipping model pull. Make sure to pull it before querying!"
    fi
fi

echo ""
echo "========================================================================"

# Step 3: Start Docker services
echo "Step 3: Starting Docker services..."
echo ""

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose down

echo ""
echo "Starting services (MySQL, Neo4j, Redis, Backend)..."
docker-compose --env-file .env -f docker-compose.yml up -d --build

echo ""
echo "Waiting for services to become healthy..."
sleep 15

# Check service status
echo ""
echo "Service Status:"
docker-compose ps

echo ""
echo "========================================================================"

# Step 4: Verify connectivity
echo "Step 4: Verifying system connectivity..."
echo ""

# Wait a bit more for backend to fully initialize
echo "Waiting for backend to initialize..."
sleep 5

# Check health endpoint
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend API is responding"
else
    echo "⚠️  Backend API is not responding yet"
    echo "   Check logs: docker logs mahiks-backend"
fi

# Check if backend can reach Ollama
echo ""
echo "Checking backend -> Ollama connection..."
sleep 2
if docker logs mahiks-backend 2>&1 | grep -q "Generation agent initialized"; then
    echo "✅ Backend successfully connected to Ollama"
else
    echo "⚠️  Backend might have issues connecting to Ollama"
    echo "   Check logs: docker logs mahiks-backend"
fi

# Check Redis cache
echo ""
echo "Checking Redis cache..."
if docker logs mahiks-backend 2>&1 | grep -q "Redis cache initialized"; then
    echo "✅ Redis cache is connected"
else
    echo "⚠️  Redis cache might not be initialized"
    echo "   Check logs: docker logs mahiks-backend"
fi

echo ""
echo "========================================================================"
echo "STARTUP COMPLETE"
echo "========================================================================"
echo ""
echo "📊 System Status:"
echo "  - API:          http://localhost:8000"
echo "  - API Docs:     http://localhost:8000/docs"
echo "  - Neo4j:        http://localhost:7474"
echo "  - Ollama Model: $MODEL (running on host)"
echo ""
echo "🧪 Quick Test Commands:"
echo ""
echo "  # Health check"
echo "  curl http://localhost:8000/health"
echo ""
echo "  # System status"
echo "  curl http://localhost:8000/status | jq"
echo ""
echo "  # Cache statistics"
echo "  curl http://localhost:8000/api/cache/stats | jq"
echo ""
echo "  # Test query (if documents are processed)"
echo "  curl -X POST http://localhost:8000/api/ask \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"question\": \"SGK nedir?\", \"include_citations\": true}' | jq"
echo ""
echo "  # Test cache (run same query twice to see caching in action)"
echo "  curl -X POST http://localhost:8000/api/ask \\"
echo "    -d '{\"question\": \"test\"}' | jq '.metadata.from_cache'"
echo ""
echo "📝 Next Steps:"
echo ""
if curl -s http://localhost:8000/status | grep -q '"documents": 0'; then
    echo "  ⚠️  No documents processed yet!"
    echo ""
    echo "  To process documents:"
    echo "  1. Add PDFs to: data/raw_documents/"
    echo "  2. Run: docker exec mahiks-backend python scripts/update_knowledge_base.py"
else
    echo "  ✅ Documents are processed and ready for queries!"
fi
echo ""
echo "🛑 To stop the system:"
echo "  docker-compose down"
echo ""
echo "📋 View logs:"
echo "  docker logs -f mahiks-backend"
echo ""
echo "========================================================================"
