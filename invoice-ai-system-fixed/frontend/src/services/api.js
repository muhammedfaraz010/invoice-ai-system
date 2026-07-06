import axios from "axios";

// CRA uses process.env.REACT_APP_* prefix
// package.json has "proxy": "http://localhost:8000" so /api requests
// are automatically forwarded to the backend during development.
const BASE_URL = process.env.REACT_APP_API_URL || "/api";

const api = axios.create({ baseURL: BASE_URL });

export const getStoredToken = () => sessionStorage.getItem("access_token") || localStorage.getItem("token");

export const getStoredUser = () => {
  const raw = sessionStorage.getItem("user");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const storeAuth = (payload) => {
  sessionStorage.setItem("access_token", payload.access_token);
  sessionStorage.setItem("refresh_token", payload.refresh_token);
  sessionStorage.setItem("user", JSON.stringify(payload.user));
  localStorage.removeItem("token");
};

export const clearAuth = () => {
  sessionStorage.removeItem("access_token");
  sessionStorage.removeItem("refresh_token");
  sessionStorage.removeItem("user");
  localStorage.removeItem("token");
};

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = getStoredToken();
  console.debug("[API]", config.method?.toUpperCase(), config.url);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const isLoginRequest = err.config?.url?.includes("/auth/login");
    if (err.response?.status === 401 && !isLoginRequest) {
      clearAuth();
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Auth
export const login = (username, password) =>
  api.post("/auth/login", { username, password });
export const register = (data) => api.post("/auth/register", data);
export const getMe = () => api.get("/auth/me");
export const updateProfile = (data) => api.put("/auth/profile", data);
export const listUsers = () => api.get("/users");
export const getUserProfile = (id) => api.get(`/users/${id}`);
export const getUserInvoices = (id, params) => api.get(`/users/${id}/invoices`, { params });
export const getUserChatHistory = (id) => api.get(`/users/${id}/chat-history`);
export const getUserActivityLog = (id) => api.get(`/users/${id}/activity-log`);
export const getUserStorage = (id) => api.get(`/users/${id}/storage`);
export const updateUser = (id, data) => api.put(`/users/${id}`, data);
export const updateUserStatus = (id, status) => api.patch(`/users/${id}/status`, { status });
export const deactivateUser = (id) => updateUserStatus(id, "Inactive");
export const requestUserDelete = (userId, reason) => api.post("/delete-user-request", { user_id: userId, reason });

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
export const requestInvoiceDelete = (invoiceId, reason) => api.post("/delete-request", { invoice_id: invoiceId, reason });
export const validateInvoice = (id) => api.get(`/validate/${id}`);
export const listDeleteRequests = () => api.get("/delete-requests");
export const listDeleteUserRequests = () => api.get("/delete-user-requests");
export const approveDelete = (requestId) => api.post("/approve-delete", { request_id: requestId });
export const rejectDelete = (requestId) => api.post("/reject-delete", { request_id: requestId });
export const approveUserDelete = (requestId) => api.post("/approve-user-delete", { request_id: requestId });
export const rejectUserDelete = (requestId) => api.post("/reject-user-delete", { request_id: requestId });
export const getNotifications = () => api.get("/notifications");
export const getAuditLog = (params) => api.get("/audit-log", { params });

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
