import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Auth
export const authAPI = {
  register: (data: { username: string; email: string; password: string }) =>
    api.post("/auth/register", data),
  login: (data: { username: string; password: string }) =>
    api.post("/auth/login", data),
  me: () => api.get("/auth/me"),
};

// Notebooks
export const notebooksAPI = {
  list: () => api.get("/notebooks"),
  get: (id: string) => api.get(`/notebooks/${id}`),
  create: (data: { name: string; description?: string }) =>
    api.post("/notebooks", data),
  update: (id: string, data: any) => api.put(`/notebooks/${id}`, data),
  delete: (id: string) => api.delete(`/notebooks/${id}`),
};

// Sources
export const sourcesAPI = {
  list: () => api.get("/sources"),
  get: (id: string) => api.get(`/sources/${id}`),
  uploadFile: (file: File, notebookId?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (notebookId) form.append("notebook_id", notebookId);
    return api.post("/sources/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  createFromURL: (url: string, notebookId?: string) =>
    api.post("/sources/url", { url, notebook_id: notebookId }),
  process: (id: string) => api.post(`/sources/${id}/process`),
  generateGuide: (id: string) => api.post(`/sources/${id}/generate-guide`),
  delete: (id: string) => api.delete(`/sources/${id}`),
};

// Notes
export const notesAPI = {
  list: () => api.get("/notes"),
  get: (id: string) => api.get(`/notes/${id}`),
  create: (data: {
    title?: string;
    content: string;
    notebook_id?: string;
    note_type?: string;
  }) => api.post("/notes", data),
  update: (id: string, data: any) => api.put(`/notes/${id}`, data),
  delete: (id: string) => api.delete(`/notes/${id}`),
};

// Chat
export const chatAPI = {
  send: (data: {
    message: string;
    notebook_id: string;
    model_override?: string;
  }) => api.post("/chat", data),
  stream: (data: {
    message: string;
    notebook_id: string;
    session_id?: string;
    model_override?: string;
  }) =>
    fetch("/api/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("token")}`,
      },
      body: JSON.stringify(data),
    }),
  sourceStream: (data: {
    message: string;
    source_id: string;
    session_id?: string;
    model_override?: string;
  }) =>
    fetch("/api/chat/source-stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("token")}`,
      },
      body: JSON.stringify(data),
    }),
};

// Chat Sessions
export const sessionsAPI = {
  searchHistory: (q: string) => api.get(`/chat/sessions/search`, { params: { q } }),
  list: (params: { source_id?: string; notebook_id?: string }) => {
    const query = new URLSearchParams();
    if (params.source_id) query.set("source_id", params.source_id);
    if (params.notebook_id) query.set("notebook_id", params.notebook_id);
    return api.get(`/chat/sessions?${query.toString()}`);
  },
  create: (data: { source_id?: string; notebook_id?: string; title?: string }) =>
    api.post("/chat/sessions", data),
  getMessages: (sessionId: string) =>
    api.get(`/chat/sessions/${sessionId}/messages`),
  update: (sessionId: string, data: { title?: string }) =>
    api.put(`/chat/sessions/${sessionId}`, data),
  delete: (sessionId: string) =>
    api.delete(`/chat/sessions/${sessionId}`),
};

// Search
export const searchAPI = {
  search: (data: {
    query: string;
    search_type?: string;
    results?: number;
  }) => api.post("/search", data),
};

// Podcasts
export const podcastsAPI = {
  listEpisodeProfiles: () => api.get("/podcasts/episode-profiles"),
  createEpisodeProfile: (data: any) =>
    api.post("/podcasts/episode-profiles", data),
  updateEpisodeProfile: (id: string, data: any) =>
    api.put(`/podcasts/episode-profiles/${id}`, data),
  deleteEpisodeProfile: (id: string) =>
    api.delete(`/podcasts/episode-profiles/${id}`),
  listSpeakerProfiles: () => api.get("/podcasts/speaker-profiles"),
  createSpeakerProfile: (data: any) =>
    api.post("/podcasts/speaker-profiles", data),
  updateSpeakerProfile: (id: string, data: any) =>
    api.put(`/podcasts/speaker-profiles/${id}`, data),
  deleteSpeakerProfile: (id: string) =>
    api.delete(`/podcasts/speaker-profiles/${id}`),
  listEpisodes: () => api.get("/podcasts/episodes"),
  getEpisode: (id: string) => api.get(`/podcasts/episodes/${id}`),
  generate: (data: any) => api.post("/podcasts/generate", data),
  updateTranscript: (id: string, dialogues: any[]) =>
    api.put(`/podcasts/episodes/${id}/transcript`, { dialogues }),
  generateAudio: (id: string) =>
    api.post(`/podcasts/episodes/${id}/generate-audio`),
  deleteEpisode: (id: string) => api.delete(`/podcasts/episodes/${id}`),
};

// Config
export const configAPI = {
  get: () => api.get("/config"),
  update: (data: {
    default_provider: string;
    default_model: string;
    google_api_key?: string;
    openai_api_key?: string;
  }) => api.put("/config", data),
  getProviders: () => api.get("/config/providers"),
};

export default api;
