import { useState } from "react";
import type { Source } from "../types";

export function SourcesPanel({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
      >
        {open ? "Hide" : "Show"} {sources.length} source{sources.length > 1 ? "s" : ""}
      </button>

      {open && (
        <ul className="mt-2 space-y-2">
          {sources.map((source, i) => (
            <li
              key={`${source.label}-${i}`}
              className="rounded-md border border-neutral-200 bg-neutral-50 p-2.5 text-xs dark:border-neutral-700 dark:bg-neutral-800"
            >
              <div className="mb-1 flex items-center gap-2">
                <span className="font-medium text-neutral-700 dark:text-neutral-200">{source.label}</span>
                <span className="ml-auto text-neutral-400">score {source.score.toFixed(2)}</span>
              </div>
              <p className="line-clamp-3 text-neutral-600 dark:text-neutral-400">{source.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
