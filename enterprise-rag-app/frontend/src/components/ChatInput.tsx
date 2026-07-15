import { useState, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  const submit = () => {
    if (!value.trim() || disabled) return;
    onSend(value.trim());
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div
        className="flex items-end gap-2 rounded-xl border p-2 shadow-sm transition-colors focus-within:shadow-md"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      >
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask a question about your ingested documents…"
          className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
          style={{ color: "var(--ink)" }}
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="shrink-0 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-40"
          style={{ backgroundColor: "var(--accent)" }}
          onMouseEnter={(e) => {
            if (!disabled && value.trim()) e.currentTarget.style.backgroundColor = "var(--accent-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "var(--accent)";
          }}
        >
          Send
        </button>
      </div>
      <p className="mt-1.5 text-[11px]" style={{ color: "var(--ink-muted)" }}>
        Enter to send · Shift+Enter for a new line
      </p>
    </div>
  );
}
