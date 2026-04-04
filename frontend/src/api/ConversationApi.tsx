import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";

// Remove trailing slash from BASE_URL if present
const BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

const conversationApi: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/conversations`,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 10000,
});

// Request interceptor to add auth token
conversationApi.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for auth errors
conversationApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ============================================
// Types
// ============================================

export interface ConversationResponse {
  id: number;
  user_id: number;
  title: string;
  message_count: number;
  last_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageResponse {
  id: number;
  conversation_id: number;
  content: string;
  sender: "user" | "agent";
  created_at: string;
}

export interface ConversationWithMessages {
  id: number;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  messages: MessageResponse[];
}

// ============================================
// API Functions
// ============================================

export const createConversation = async (title?: string): Promise<number> => {
  const response = await conversationApi.post("", { title: title || "Yeni Sohbet" });
  return response.data.data.conversation_id;
};

export const getConversations = async (): Promise<ConversationResponse[]> => {
  const response = await conversationApi.get("");
  return response.data.data;
};

export const getConversation = async (conversationId: number): Promise<ConversationWithMessages> => {
  const response = await conversationApi.get(`/${conversationId}`);
  return response.data.data;
};

export const updateConversationTitle = async (conversationId: number, title: string): Promise<void> => {
  await conversationApi.patch(`/${conversationId}`, { title });
};

export const deleteConversation = async (conversationId: number): Promise<void> => {
  await conversationApi.delete(`/${conversationId}`);
};

export const addMessage = async (
  conversationId: number,
  content: string,
  sender: "user" | "agent"
): Promise<number> => {
  const response = await conversationApi.post(`/${conversationId}/messages`, {
    content,
    sender,
  });
  return response.data.data.message_id;
};

export const getMessages = async (conversationId: number): Promise<MessageResponse[]> => {
  const response = await conversationApi.get(`/${conversationId}/messages`);
  return response.data.data;
};

export default conversationApi;