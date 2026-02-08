"""
Pydantic schemas for API request/response validation
"""
import uuid
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy import func
from sqlalchemy.dialects.mysql import BIGINT

class UserResponse(BaseModel):
    """User response model"""
    id: int
    display_name: str
    email: str
    status: str

    class Config:
        from_attributes = True

class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    question: str = Field(..., min_length=1, description="User's question")
    include_citations: bool = Field(True, description="Include source citations")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")
    conversation_id: Optional[int] = Field(None, description="Conversation ID for context-aware responses")


class SourceInfo(BaseModel):
    """Information about a source document"""
    name: str
    type: str
    relevance: float


class QueryMetadata(BaseModel):
    """Metadata about query processing"""
    response_time_ms: int
    chunks_retrieved: int
    facts_retrieved: int
    model: str
    success: bool = True


class Citation(BaseModel):
    """Citation information"""
    source: str
    type: str
    similarity: float
    ce_score: Optional[float] = None


class QueryResponse(BaseModel):
    """Response model for query endpoint"""
    query: str
    answer: str
    citations: List[Citation] = []
    sources: Dict = {}
    metadata: QueryMetadata
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str


class StatusResponse(BaseModel):
    """System status response"""
    status: str
    documents: int
    chunks: int
    vectors: int
    graph: Dict
    components: Dict
    error: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    """Document upload response"""
    success: bool
    message: str
    document_id: Optional[int] = None
    chunks_created: int = 0
    triplets_extracted: int = 0


class BatchQueryRequest(BaseModel):
    """Batch query request"""
    queries: List[str] = Field(..., min_items=1, max_items=10)


class BatchQueryResponse(BaseModel):
    """Batch query response"""
    results: List[QueryResponse]
    total_queries: int
    successful: int
    failed: int
