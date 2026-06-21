// Thin typed wrapper around the backend so components never call fetch()
// directly — one place to change if the response shape evolves.
export type ChatResponse = {
  agent: "knowledge_agent" | "sql_agent";
  answer?: string;
  sources?: { doc_id: string; chunk_id: string; score: number }[];
  sql?: string;
  rows?: Record<string, unknown>[];
  row_count?: number;
};

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }
  return res.json();
}

export async function uploadDocument(file: File): Promise<unknown> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: formData });
  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status}`);
  }
  return res.json();
}
