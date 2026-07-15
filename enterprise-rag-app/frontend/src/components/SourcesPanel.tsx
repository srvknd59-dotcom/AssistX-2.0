import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ContentType, Source } from "../types";

const TYPE_LABEL: Record<ContentType, string> = {
  text: "Text",
  table: "Table",
  image: "Image",
};

export function SourcesPanel({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;

  return (
    <div className="mt-2 not-prose">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-medium hover:underline"
        style={{ color: "var(--accent)" }}
      >
        <span className="flex -space-x-1">
          {sources.slice(0, 3).map((_, i) => (
            <span
              key={i}
              className="flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-semibold text-white"
              style={{ backgroundColor: "var(--accent)", boxShadow: "0 0 0 2px var(--surface)" }}
            >
              {i + 1}
            </span>
          ))}
        </span>
        {open ? "Hide" : "Show"} {sources.length} source{sources.length > 1 ? "s" : ""}
      </button>

      {open && (
        <ul className="mt-2 space-y-2">
          {sources.map((source, i) => (
            <li
              key={`${source.label}-${i}`}
              className="rounded-lg border p-3 text-xs"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            >
              <div className="mb-1.5 flex flex-wrap items-center gap-2">
                <span
                  className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-semibold text-white"
                  style={{ backgroundColor: "var(--accent)" }}
                >
                  {i + 1}
                </span>
                <span className="font-medium" style={{ color: "var(--ink)" }}>
                  {source.label}
                </span>
                {source.content_type !== "text" && (
                  <span
                    className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                    style={{ backgroundColor: "var(--accent-soft)", color: "var(--accent-ink)" }}
                  >
                    {TYPE_LABEL[source.content_type]}
                  </span>
                )}
                {source.page != null && (
                  <span className="text-[10px]" style={{ color: "var(--ink-muted)" }}>
                    p.{source.page}
                  </span>
                )}
                <span className="ml-auto tabular-nums" style={{ color: "var(--ink-muted)" }}>
                  score {source.score.toFixed(2)}
                </span>
              </div>
              <SourceSnippet source={source} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SourceSnippet({ source }: { source: Source }) {
  if (source.content_type === "table") {
    return (
      <div className="prose prose-xs dark:prose-invert max-w-none" style={{ color: "var(--ink-muted)" }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{source.snippet}</ReactMarkdown>
      </div>
    );
  }

  if (source.content_type === "image") {
    const caption = source.snippet.replace(/^\[Image[^\]]*\]:\s*/, "");
    return (
      <p className="line-clamp-3 italic" style={{ color: "var(--ink-muted)" }}>
        {caption}
      </p>
    );
  }

  return (
    <p className="line-clamp-3" style={{ color: "var(--ink-muted)" }}>
      {source.snippet}
    </p>
  );
}
