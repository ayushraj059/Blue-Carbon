import axios from "axios";

const isLocalDev = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
const API_BASE =
  process.env.REACT_APP_API_URL ||
  (isLocalDev ? "http://127.0.0.1:8000/api" : "/api");
const WS_BASE =
  process.env.REACT_APP_WS_URL ||
  (isLocalDev
    ? "ws://127.0.0.1:8000"
    : (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host);

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export const uploadCSV = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
};

export const getPipelineStatus = (runId) => api.get(`/pipeline/${runId}`);

export const getCredits = (limit = 20, offset = 0) =>
  api.get(`/credits?limit=${limit}&offset=${offset}`);

export const getCredit = (projectId) => api.get(`/credit/${encodeURIComponent(projectId)}`);

export const getOpsMetrics = () => api.get("/ops");

export const mapSnapshot = (body) => api.post("/map-snapshot", body);

export const analyzeImage = (imageFile, location, areaHectares) => {
  const form = new FormData();
  form.append("image", imageFile);
  form.append("location", location);
  form.append("area_hectares", areaHectares);
  return api.post("/upload-image", form, { headers: { "Content-Type": "multipart/form-data" } });
};

export const createWebSocket = (runId, onMessage, onClose) => {
  const ws = new WebSocket(`${WS_BASE}/ws/pipeline/${runId}`);
  ws.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data));
    } catch (_) {}
  };
  ws.onclose = () => onClose && onClose();
  ws.onerror = (e) => console.error("WebSocket error", e);
  return ws;
};

export default api;
