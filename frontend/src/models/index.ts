// ============================================
// API Response Wrapper (matches backend ApiResponse)
// ============================================

export interface ApiResponse<T> {
    status: number;
    message: string;
    data: T;
}

// ============================================
// Chat Models
// ============================================

export interface QueryRequest {
    question: string;
    include_citations?: boolean;
    top_k?: number;
    conversation_id?: string;
}

export interface ChatResponse {
    answer: string;
    citations?: Citation[];
    confidence?: number;
    conversation_id?: string;
}

export interface Citation {
    index?: number;
    source: string;
    section_number?: string;
    section_title?: string;
    content: string;
    relevance_score?: number;
    document_type?: 'pdf' | 'html' | 'txt';
}

// ============================================
// User Models
// ============================================

export interface User {
    id: string;
    email: string;
    display_name: string;
    created_at?: string;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
    user: User;
}

// AuthResponse is alias for LoginResponse (used in login endpoint)
export type AuthResponse = LoginResponse;

// ============================================
// Conversation Models
// ============================================

export interface SubChunk {
    text: string;
    source: string;
    ce_score: number;
    similarity: number;
}

export interface RagMetadata {
    chunks_retrieved: number;
    facts_retrieved: number;
    retrieval_time_ms: number;
    sub_chunks: SubChunk[];
    model: string;
}

export interface Message {
    id: string;
    content: string;
    sender: 'user' | 'agent';
    timestamp: Date;
    isLoading?: boolean;
    citations?: Citation[];
    ragMetadata?: RagMetadata;
}

export interface Conversation {
    id: string;
    title: string;
    lastMessage: string;
    timestamp: Date;
    messageCount: number;
}

export interface ConversationData {
    id: string;
    messages: Message[];
    customTitle?: string;
}

// ============================================
// API Error Models
// ============================================

export interface ApiError {
    detail: string;
    status_code?: number;
}

// ============================================
// Helper function to create query request
// ============================================

export const createQueryRequest = (
    question: string,
    options?: {
        include_citations?: boolean;
        top_k?: number;
        conversation_id?: string;
    }
): QueryRequest => ({
    question,
    include_citations: options?.include_citations ?? true,
    top_k: options?.top_k ?? 5,
    conversation_id: options?.conversation_id,
});