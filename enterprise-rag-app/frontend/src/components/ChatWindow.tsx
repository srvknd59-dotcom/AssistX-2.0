import { useEffect, useRef } from "react";
import { useChat } from "../hooks/useChat";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

export function ChatWindow() {
  const { messages, isSending, error, sendMessage } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex min-w-0 flex-1 flex-col" style={{ backgroundColor: "var(--bg)" }}>
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
          {messages.length === 0 && <EmptyState />}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {error && (
            <div
              className="rounded-lg border px-3 py-2 text-xs"
              style={{ borderColor: "var(--critical)", backgroundColor: "var(--critical-soft)", color: "var(--critical)" }}
            >
              {error}
            </div>
          )}
        </div>
      </div>
      <div className="mx-auto w-full max-w-3xl">
        <ChatInput onSend={sendMessage} disabled={isSending} />
      </div>
    </div>
  );
}

function EmptyState() {
  const suggestions = [
    "How do I pair the GlowMug with the app?",
    "What's the return window for a GlowMug?",
    "Is the GlowMug dishwasher safe?",
    "Can I work remotely more than 3 days a week?",
  ];

  return (
    <div className="flex h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div
        className="flex h-12 w-12 items-center justify-center rounded-2xl text-xl"
        style={{ backgroundColor: "var(--accent-soft)" }}
      >
        🔎
      </div>
      <div>
        <h3 className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
          Ask a question grounded in your ingested documents
        </h3>
        <p className="mt-1 text-xs" style={{ color: "var(--ink-muted)" }}>
          Try one of these:
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {suggestions.map((s) => (
          <span
            key={s}
            className="rounded-full border px-3 py-1 text-xs"
            style={{ borderColor: "var(--border)", color: "var(--ink-muted)" }}
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}
