import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const api = axios.create({ baseURL: BASE_URL });

// Attach JWT token if present.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/";
    }
    return Promise.reject(err);
  }
);

// Auth
export const login = (username, password) =>
  api.post("/auth/login", { username, password });

export const register = (data) => api.post("/auth/register", data);
export const getMe = () => api.get("/auth/me");

// Invoices
export const uploadInvoice = (file, onProgress) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
  });
};

export const getInvoice = (id) => api.get(`/invoice/${id}`);
export const listInvoices = (params) => api.get("/invoices", { params });
export const deleteInvoice = (id) => api.delete(`/invoice/${id}`);
export const validateInvoice = (id) => api.get(`/validate/${id}`);

// RAG Chat
export const queryChatbot = (question, sessionId) =>
  api.post("/query", { question, session_id: sessionId });

export const getChatHistory = () => api.get("/chat-history");

// Agent Actions
export const getAgentActions = (params) => api.get("/agent-actions", { params });
export const resolveAction = (id) => api.post(`/agent-action/${id}/resolve`);

// Analytics
export const getAnalytics = () => api.get("/analytics");

// Health
export const getHealth = () => api.get("/health");
