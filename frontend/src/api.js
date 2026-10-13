import axios from "axios";

// Empty baseURL = same origin (Vite dev proxy or backend-served build).
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "", timeout: 120000 });

/** Turn any axios error into a short, friendly message. */
export function friendlyError(err) {
  if (err?.response) {
    const d = err.response.data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => x.msg).join(", ");
    return `Request failed (${err.response.status}). Please try again.`;
  }
  if (err?.code === "ECONNABORTED") return "The server took too long to respond. Please try again.";
  return "Can't reach the InternAI server. Make sure the backend is running (port 8000) and try again.";
}

export const uploadResume = (file, onProgress) => {
  const form = new FormData();
  form.append("file", file);
  return api
    .post("/api/upload", form, {
      onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
    })
    .then((r) => r.data);
};
export const getAnalysis = (id) => api.get(`/api/analysis/${id}`).then((r) => r.data);
export const whatIf = (analysisId, role, extraSkills) =>
  api.post("/api/whatif", { analysis_id: analysisId, role, extra_skills: extraSkills }).then((r) => r.data);
export const getRoadmap = (id, role) => api.get(`/api/roadmap/${id}`, { params: { role } }).then((r) => r.data);
export const searchSkills = (q) => api.get("/api/skills", { params: { q, limit: 8 } }).then((r) => r.data);
export const deleteAnalysis = (id) => api.delete(`/api/analysis/${id}`);
