import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { QueryRequest, ApiError } from "../models";

// Backend QueryResponse type (matches backend schema)
interface BackendQueryResponse {
  query: string;
  answer: string;
  citations: Array<{
    source: string;
    section_number?: string;
    section_title?: string;
    type: string;
    similarity: number;
    ce_score?: number;
  }>;
  sources: Record<string, unknown>;
  metadata: {
    response_time_ms: number;
    chunks_retrieved: number;
    facts_retrieved: number;
    model: string;
    success: boolean;
  };
  error?: string;
}

// Frontend ChatResponse type
export interface ChatResponse {
  answer: string;
  citations?: Array<{
    source: string;
    section_number?: string;
    section_title?: string;
    content: string;
    relevance_score?: number;
  }>;
  confidence?: number;
}

// Remove trailing slash from BASE_URL if present
const BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

const chatApi: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api`,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 120000, // 2 minutes timeout for LLM responses
});

// Request interceptor to add auth token
chatApi.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for global error handling
chatApi.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear and redirect to login
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export const chatRequest = async (queryRequest: QueryRequest): Promise<ChatResponse> => {
  const response = await chatApi.post<BackendQueryResponse>("/ask", queryRequest);
  
  // Transform backend response to frontend format
  const backendData = response.data;
  
  return {
    answer: backendData.answer,
    citations: backendData.citations?.map(c => ({
      source: c.source,
      section_number: c.section_number,
      section_title: c.section_title,
      content: c.type,
      relevance_score: c.similarity
    })),
    confidence: backendData.metadata?.success ? 1.0 : 0.0
  };
};

// Streaming chat request using SSE (Server-Sent Events)
export const chatRequestStream = async (
  queryRequest: QueryRequest,
  onChunk: (chunk: string) => void,
  onMetadata?: (metadata: Record<string, unknown>) => void,
  onCitations?: (citations: Array<{
    index?: number;
    source: string;
    section_number?: string;
    section_title?: string;
    content?: string;
    document_type?: string;
    relevance_score?: number;
    // legacy fields, still tolerated:
    type?: string;
    similarity?: number;
    ce_score?: number | null;
  }>) => void,
  onDone?: (data: {
    response_time_ms: number;
    answer: string;
    graph_facts?: Array<
      | { type: 'triplet'; source: string; rel: string; target: string; labels?: string[] }
      | { type: 'path'; nodes: string[]; rels: string[] }
    >;
  }) => void,
  onError?: (error: string) => void,
  onConfidence?: (data: {
    level: 'low' | 'normal';
    max_ce: number | null;
    mean_ce: number | null;
    passed_chunks: number;
    ce_floor: number;
    min_chunks: number;
  }) => void,
): Promise<void> => {
  const token = localStorage.getItem("token");

  const response = await fetch(`${BASE_URL}/api/ask/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(queryRequest),
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    onError?.(`HTTP ${response.status}: ${response.statusText}`);
    return;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;

      try {
        const event = JSON.parse(line.slice(6));
        switch (event.type) {
          case "chunk":
            onChunk(event.data);
            break;
          case "metadata":
            onMetadata?.(event.data);
            break;
          case "citations":
            onCitations?.(event.data);
            break;
          case "confidence":
            onConfidence?.(event.data);
            break;
          case "done":
            onDone?.(event.data);
            break;
          case "error":
            onError?.(event.data?.message || "Unknown error");
            break;
        }
      } catch {
        // Skip malformed JSON
      }
    }
  }
};

// Optional: Batch query endpoint
export const batchChatRequest = async (queries: QueryRequest[]): Promise<ChatResponse[]> => {
  const response = await chatApi.post<{ results: BackendQueryResponse[] }>("/batch-ask", { queries });
  
  return response.data.results.map(backendData => ({
    answer: backendData.answer,
    citations: backendData.citations?.map(c => ({
      source: c.source,
      section_number: c.section_number,
      section_title: c.section_title,
      content: c.type,
      relevance_score: c.similarity
    })),
    confidence: backendData.metadata?.success ? 1.0 : 0.0
  }));
};

export default chatApi;