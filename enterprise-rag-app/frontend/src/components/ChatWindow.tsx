import { Search } from "lucide-react";
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
          {messages.length === 0 && <EmptyState onPick={sendMessage} />}
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

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  const suggestions = [
    "How do I pair the GlowMug with the app?",
    "What's the return window for a GlowMug?",
    "Is the GlowMug dishwasher safe?",
    "Can I work remotely more than 3 days a week?",
  ];

  return (
    <div className="flex h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div
        className="brand-mark flex h-12 w-12 items-center justify-center rounded-2xl text-white"
        style={{ boxShadow: "var(--shadow-md)" }}
      >
        <Search className="h-5 w-5" strokeWidth={2} />
      </div>
      <div>
        <h3 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
          Ask anything about your documents
        </h3>
        <p className="mt-1 text-xs" style={{ color: "var(--ink-muted)" }}>
          Every answer is grounded and cited. Try one of these:
        </p>
      </div>
      <div className="flex max-w-lg flex-wrap justify-center gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="rounded-full border px-3 py-1.5 text-xs transition-colors hover:border-transparent hover:text-white"
            style={{ borderColor: "var(--border)", color: "var(--ink-muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--accent)")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
