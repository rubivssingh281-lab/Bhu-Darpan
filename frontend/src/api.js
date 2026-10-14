import axios from "axios";

// When VITE_API_BASE is empty we rely on the Vite dev proxy (/api, /storage).
const rawBase = import.meta.env.VITE_API_BASE || "";
const BASE = rawBase.endsWith("/") ? rawBase.slice(0, -1) : rawBase;

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
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${BASE}${cleanPath}`;
}

export default api;
