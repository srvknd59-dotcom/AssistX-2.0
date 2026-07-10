import { useCallback, useEffect, useState } from "react";
import { sendChatMessage, startChatSession } from "../api/client";
import type { ChatMessage } from "../types";

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useChat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    startChatSession()
      .then(setSessionId)
      .catch(() => setError("Could not start a chat session. Is the backend running on :8000?"));
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || isSending) return;

      setError(null);
      const userMessage: ChatMessage = { id: makeId(), role: "user", content: text };
      const pendingMessage: ChatMessage = { id: makeId(), role: "assistant", content: "", pending: true };
      setMessages((prev) => [...prev, userMessage, pendingMessage]);
      setIsSending(true);

      try {
        const result = await sendChatMessage(sessionId, text);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingMessage.id
              ? { ...m, content: result.answer, sources: result.sources, pending: false }
              : m,
          ),
        );
      } catch {
        setMessages((prev) => prev.filter((m) => m.id !== pendingMessage.id));
        setError("The request failed. Check that the backend is running and OPENAI_API_KEY is set.");
      } finally {
        setIsSending(false);
      }
    },
    [sessionId, isSending],
  );

  return { sessionId, messages, isSending, error, sendMessage };
}
