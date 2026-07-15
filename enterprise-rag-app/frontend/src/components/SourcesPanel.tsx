import { useState } from "react";
import type { Source } from "../types";

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
              <div className="mb-1.5 flex items-center gap-2">
                <span
                  className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-semibold text-white"
                  style={{ backgroundColor: "var(--accent)" }}
                >
                  {i + 1}
                </span>
                <span className="font-medium" style={{ color: "var(--ink)" }}>
                  {source.label}
                </span>
                <span className="ml-auto tabular-nums" style={{ color: "var(--ink-muted)" }}>
                  score {source.score.toFixed(2)}
                </span>
              </div>
              <p className="line-clamp-3" style={{ color: "var(--ink-muted)" }}>
                {source.snippet}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
