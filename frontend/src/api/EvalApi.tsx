import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";

const BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

const evalApi: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/eval`,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

evalApi.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

evalApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// ============================================
// Types — mirror the JSON written by scripts/evaluate_api.py
// ============================================

export interface IrMetrics {
  "hit@1": number;
  "hit@3": number;
  "hit@5": number;
  "hit@10": number;
  mrr: number;
  map: number;
  "ndcg@5": number;
  "ndcg@10": number;
}

export interface LatencyStats {
  mean_ms: number;
  median_ms: number;
  p95_ms: number;
  p99_ms: number;
  min_ms: number;
  max_ms: number;
}

export interface RetrievalSummary {
  evaluated: number;
  total: number;
  stage1_vector: IrMetrics;
  stage2_full_pipeline: IrMetrics;
  latency: LatencyStats;
}

export interface GenerationSummary {
  evaluated: number;
  total: number;
  avg_faithfulness: number;
  avg_answer_relevance: number;
  avg_context_precision: number;
  avg_context_recall: number;
}

export interface ReportSummary {
  retrieval: RetrievalSummary;
  generation: GenerationSummary;
  generation_latency?: LatencyStats;
}

export interface ReportListItem {
  filename: string;
  timestamp?: string;
  api_url?: string;
  judge?: { provider: string; model: string };
  questions_file?: string;
  summary?: ReportSummary;
  error?: string;
}

export interface PerQuestionResult {
  id: number;
  question: string;
  ground_truth?: string;
  source_chunk_id?: number;
  retrieval?: {
    latency_ms?: number;
    stage1_rank?: number | null;
    stage2_rank?: number | null;
  };
  generation?: {
    answer?: string;
    wall_latency_ms?: number;
    server_latency_ms?: number;
    judge_scores?: {
      faithfulness?: number;
      answer_relevance?: number;
      context_precision?: number;
      context_recall?: number;
      [k: string]: number | undefined;
    };
  };
}

export interface FullReport {
  timestamp: string;
  api_url?: string;
  questions_file?: string;
  top_k?: number;
  judge?: { provider: string; model: string };
  summary: ReportSummary;
  results: PerQuestionResult[];
}

// ============================================
// API functions
// ============================================

export const listReports = async (): Promise<ReportListItem[]> => {
  const response = await evalApi.get("/reports");
  return response.data.data;
};

export const getReport = async (filename: string): Promise<FullReport> => {
  const response = await evalApi.get(`/reports/${encodeURIComponent(filename)}`);
  return response.data.data;
};

export default evalApi;
