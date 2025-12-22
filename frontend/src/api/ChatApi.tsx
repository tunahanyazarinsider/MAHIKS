import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { QueryRequest, ChatResponse, ApiError } from "../models";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
  const response = await chatApi.post<ChatResponse>("/ask", queryRequest);
  return response.data;
};

// Optional: Batch query endpoint
export const batchChatRequest = async (queries: QueryRequest[]): Promise<ChatResponse[]> => {
  const response = await chatApi.post<ChatResponse[]>("/batch-ask", { queries });
  return response.data;
};

// Optional: Get chat history
export const getChatHistory = async (conversationId: string): Promise<ChatResponse[]> => {
  const response = await chatApi.get<ChatResponse[]>(`/history/${conversationId}`);
  return response.data;
};

export default chatApi;
