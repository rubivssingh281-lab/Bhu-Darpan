import axios from "axios";

// When VITE_API_BASE is empty we rely on the Vite dev proxy (/api, /storage).
const BASE = import.meta.env.VITE_API_BASE || "";

export const api = axios.create({ baseURL: BASE });

// Attach JWT from localStorage to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("bd_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Resolve a backend-relative media path (/storage/...) to a full URL.
export function mediaUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//.test(path)) return path;
  return `${BASE}${path}`;
}

export default api;
