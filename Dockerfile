# Multi-stage Dockerfile for MAHIKS-TR Backend

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy Turkish model (optional, will auto-download on first use if missing)
# Using || true to make this non-fatal - the KG agent will download it when needed
RUN python -m spacy download tr_core_news_lg || echo "Warning: spaCy model download failed, will download on first use"

# Copy application code
COPY backend/ ./backend/
COPY scripts/ ./scripts/
# It copies the .env.example file to .env and the values inside the .env.example will be used as default environment variables.
COPY .env.example .env

# Create data directories
RUN mkdir -p /app/data/raw_documents /app/chroma_data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
