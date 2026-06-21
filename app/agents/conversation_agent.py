"""
ConversationAgent — handles greetings, meta-questions ("what can you do?"),
follow-ups, and anything that doesn't belong to SQL or RAG.

This is the "face" of the assistant: it maintains tone, explains capabilities,
and keeps the interaction feeling like a real product rather than a demo.
It also receives conversation history so responses are context-aware.
"""
from app.core.llm_client import LLMClient

SYSTEM_PROMPT = """CONVERSATION: You are an enterprise AI operations assistant built for a logistics and operations company.

You have three specialized agents at your disposal:
- KnowledgeAgent: answers questions about uploaded documents (HR policies, SOPs, reports)
- SQLAgent: runs natural language queries against the operations database (shipments, delays, routes)
- AnalyticsAgent: computes trends, summaries, anomalies, and KPIs from operations data

Respond naturally and helpfully. When the user greets you, welcome them warmly and briefly explain what you can do.
When they ask what you can do, give a clear, professional overview with examples.
When they ask follow-up questions, use the conversation history for context.
Keep responses concise but complete. Use bullet points for lists. Be professional but friendly.
Never say you "don't know" without offering an alternative path."""


class ConversationAgent:
    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    def respond(self, message: str, history: list[dict] | None = None) -> dict:
        history_text = ""
        if history:
            recent = history[-6:]
            history_text = "\n".join(
                f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['text']}"
                for h in recent
            )
            user_prompt = f"Conversation so far:\n{history_text}\n\nUser: {message}"
        else:
            user_prompt = message

        answer = self.llm.chat(system=SYSTEM_PROMPT, user=user_prompt)
        return {"answer": answer, "sources": None}
