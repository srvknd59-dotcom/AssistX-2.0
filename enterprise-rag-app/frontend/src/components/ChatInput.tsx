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
    <div className="border-t border-black/10 bg-white p-4 dark:border-white/10 dark:bg-neutral-900">
      <div className="flex items-end gap-2 rounded-xl border border-neutral-300 bg-neutral-50 p-2 focus-within:border-indigo-500 dark:border-neutral-700 dark:bg-neutral-800">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask about a manual or a past support ticket…"
          className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-neutral-900 outline-none placeholder:text-neutral-400 dark:text-neutral-100"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="shrink-0 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Send
        </button>
      </div>
      <p className="mt-1.5 text-[11px] text-neutral-400">Enter to send · Shift+Enter for a new line</p>
    </div>
  );
}
