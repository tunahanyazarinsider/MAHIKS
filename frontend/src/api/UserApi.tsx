import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { User, LoginResponse, ApiResponse } from "../models";

// Request types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

export interface UpdateProfileRequest {
  name?: string;
  email?: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const userApi: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 10000,
});

// Request interceptor to add auth token for protected routes
userApi.interceptors.request.use(
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

// Auth endpoints (public)
export const login = async (email: string, password: string): Promise<LoginResponse> => {
  const response = await userApi.post<ApiResponse<LoginResponse>>("/login", { email, password });
  return response.data.data;
};

export const register = async (
  name: string,
  email: string,
  password: string
): Promise<LoginResponse> => {
  const response = await userApi.post<ApiResponse<LoginResponse>>("/register", { name, email, password });
  return response.data.data;
};

// Protected endpoints (require token)
export const getProfile = async (): Promise<User> => {
  const response = await userApi.get<ApiResponse<User>>("/profile");
  return response.data.data;
};

export const updateProfile = async (data: UpdateProfileRequest): Promise<User> => {
  const response = await userApi.put<ApiResponse<User>>("/profile", data);
  return response.data.data;
};

export const changePassword = async (
  currentPassword: string,
  newPassword: string
): Promise<void> => {
  await userApi.post<ApiResponse<null>>("/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
};

export const logout = async (): Promise<void> => {
  try {
    await userApi.post<ApiResponse<null>>("/logout");
  } finally {
    localStorage.removeItem("token");
  }
};

// Token validation
export const validateToken = async (): Promise<boolean> => {
  try {
    await userApi.get<ApiResponse<User>>("/validate-token");
    return true;
  } catch {
    localStorage.removeItem("token");
    return false;
  }
};

export default userApi;