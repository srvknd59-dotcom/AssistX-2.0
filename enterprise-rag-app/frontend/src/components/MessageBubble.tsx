import { Check, Copy, Sparkles } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../types";
import { SourcesPanel } from "./SourcesPanel";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[75%] rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed text-white"
          style={{ backgroundColor: "var(--accent)" }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div
        className="brand-mark mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white"
        style={{ boxShadow: "var(--shadow-sm)" }}
      >
        <Sparkles className="h-3.5 w-3.5" strokeWidth={2.25} />
      </div>
      <div className="min-w-0 flex-1">
        {message.pending ? (
          <TypingDots />
        ) : (
          <>
            <AnswerMarkdown content={message.content} />
            {message.sources && <SourcesPanel sources={message.sources} />}
          </>
        )}
      </div>
    </div>
  );
}

function AnswerMarkdown({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="group/answer">
      <div
        className="answer-prose prose prose-sm dark:prose-invert max-w-none text-[15px] leading-relaxed"
        style={{ color: "var(--ink)" }}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
      <button
        onClick={copy}
        className="mt-1.5 flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium opacity-0 transition-opacity group-hover/answer:opacity-100 hover:bg-black/5 dark:hover:bg-white/10"
        style={{ color: "var(--ink-muted)" }}
      >
        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="flex gap-1 py-1.5">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-bounce rounded-full"
          style={{ backgroundColor: "var(--ink-muted)", animationDelay: `${i * 0.12}s` }}
        />
      ))}
    </span>
  );
}
