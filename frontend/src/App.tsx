import { useState } from "react";
import { sendChatMessage, uploadDocument, ChatResponse } from "./api";

type Message = {
  role: "user" | "assistant";
  text: string;
  meta?: ChatResponse;
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    if (!input.trim()) return;
    const question = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);
    try {
      const result = await sendChatMessage(question);
      const text =
        result.agent === "sql_agent"
          ? `Ran SQL (${result.row_count} rows):\n${result.sql}`
          : result.answer ?? "(no answer)";
      setMessages((prev) => [...prev, { role: "assistant", text, meta: result }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Error: ${(err as Error).message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadDocument(file);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", text: `Ingested "${file.name}" into the knowledge base.` },
    ]);
  }

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 20 }}>Enterprise GenAI Operations Assistant</h1>
      <p style={{ color: "#666", fontSize: 14 }}>
        Ask about uploaded documents (RAG) or operations data (NL2SQL) — one chat box,
        routed automatically.
      </p>

      <input type="file" onChange={handleUpload} style={{ marginBottom: 16 }} />

      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          minHeight: 300,
          marginBottom: 16,
        }}
      >
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <strong>{m.role === "user" ? "You" : `Assistant (${m.meta?.agent ?? "..."})`}:</strong>
            <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit" }}>{m.text}</pre>
          </div>
        ))}
        {loading && <div style={{ color: "#999" }}>Thinking…</div>}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="What is the leave policy? / Show delayed shipments last month"
          style={{ flex: 1, padding: 8 }}
        />
        <button onClick={handleSend} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  );
}
