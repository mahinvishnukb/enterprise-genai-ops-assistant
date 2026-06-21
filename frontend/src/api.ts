export type ChatResponse = {
  agent: "knowledge_agent" | "sql_agent" | "analytics_agent" | "conversation_agent";
  answer?: string;
  sources?: { doc_id: string; chunk_id: string; score: number }[];
  sql?: string;
  rows?: Record<string, unknown>[];
  row_count?: number;
  metrics?: Record<string, string | number>;
  analysis_type?: string;
};

export type UploadResponse = { doc_id: string; filename: string; chunk_count: number };

export type StatsResponse = {
  db_rows: number;
  chunk_count: number;
  queries_this_session: number;
};

const BASE = import.meta.env.VITE_API_URL ?? "";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export function sendChatMessage(message: string, history?: {role: string; text: string}[]): Promise<ChatResponse> {
  return req("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
}

export function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return req("/api/upload", { method: "POST", body: formData });
}

export function fetchStats(): Promise<StatsResponse> {
  return req("/api/stats");
}

export type DocumentInfo = { doc_id: string; chunk_count: number; source: "builtin" | "uploaded" };

export function fetchDocuments(): Promise<DocumentInfo[]> {
  return req("/api/documents");
}
