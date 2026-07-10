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
    <div className="flex min-w-0 flex-1 flex-col">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-6">
        {messages.length === 0 && <EmptyState />}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-900/30 dark:text-red-300">
            {error}
          </div>
        )}
      </div>
      <ChatInput onSend={sendMessage} disabled={isSending} />
    </div>
  );
}

function EmptyState() {
  const suggestions = [
    "How do I pair the GlowMug with the app?",
    "What's the return window for a GlowMug?",
    "A customer's GlowMug shows a solid red light — what do I check?",
    "Can I work remotely more than 3 days a week?",
  ];

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div className="text-3xl">🔎</div>
      <div>
        <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-200">
          Ask a question grounded in your manuals and tickets
        </h3>
        <p className="mt-1 text-xs text-neutral-400">Try one of these:</p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {suggestions.map((s) => (
          <span
            key={s}
            className="rounded-full border border-neutral-200 px-3 py-1 text-xs text-neutral-500 dark:border-neutral-700 dark:text-neutral-400"
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}
