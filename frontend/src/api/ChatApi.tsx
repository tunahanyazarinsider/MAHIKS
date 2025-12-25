import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { QueryRequest, ApiError } from "../models";

// Backend QueryResponse type (matches backend schema)
interface BackendQueryResponse {
  query: string;
  answer: string;
  citations: Array<{
    source: string;
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
  timeout: 30000, // 30 seconds timeout for LLM responses
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
      content: c.type,
      relevance_score: c.similarity
    })),
    confidence: backendData.metadata?.success ? 1.0 : 0.0
  };
};

// Optional: Batch query endpoint
export const batchChatRequest = async (queries: QueryRequest[]): Promise<ChatResponse[]> => {
  const response = await chatApi.post<{ results: BackendQueryResponse[] }>("/batch-ask", { queries });
  
  return response.data.results.map(backendData => ({
    answer: backendData.answer,
    citations: backendData.citations?.map(c => ({
      source: c.source,
      content: c.type,
      relevance_score: c.similarity
    })),
    confidence: backendData.metadata?.success ? 1.0 : 0.0
  }));
};

export default chatApi;