import { useRef, useState, type ReactNode } from "react";
import { uploadDocument } from "../api/client";
import type { DocumentInfo, HealthStatus } from "../types";

interface SidebarProps {
  health: HealthStatus | null;
  documents: DocumentInfo[];
  onUploaded: () => void;
}

export function Sidebar({ health, documents, onUploaded }: SidebarProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setUploading(true);
    setUploadMsg(null);
    try {
      await uploadDocument(file);
      setUploadMsg(`Uploaded "${file.name}". Click "Rebuild index" to add it to search.`);
      onUploaded();
    } catch {
      setUploadMsg(`Failed to upload "${file.name}". Supported types: .txt, .md, .pdf`);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  return (
    <aside
      className="hidden w-72 shrink-0 flex-col gap-6 overflow-y-auto border-r p-5 md:flex"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <section>
        <SectionLabel>Vector database</SectionLabel>
        <div className="grid grid-cols-3 gap-2">
          <StatTile value={health?.chunks_indexed ?? 0} label="chunks" />
          <StatTile value={health?.tables_indexed ?? 0} label="tables" />
          <StatTile value={health?.images_indexed ?? 0} label="images" />
        </div>
      </section>

      <section>
        <SectionLabel>Documents ({documents.length})</SectionLabel>
        <ul className="space-y-1">
          {documents.map((doc) => (
            <li
              key={doc.name}
              className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-black/[0.03] dark:hover:bg-white/[0.05]"
              style={{ color: "var(--ink)" }}
            >
              <span className="truncate">{doc.name}</span>
              <span
                className="ml-2 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium tabular-nums"
                style={{ backgroundColor: "var(--accent-soft)", color: "var(--accent-ink)" }}
              >
                {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"}
              </span>
            </li>
          ))}
          {documents.length === 0 && (
            <li className="text-xs" style={{ color: "var(--ink-muted)" }}>
              Not indexed yet — click "Rebuild index" above.
            </li>
          )}
        </ul>
      </section>

      <section>
        <SectionLabel>Add a document</SectionLabel>
        <input
          ref={fileInput}
          type="file"
          accept=".txt,.md,.pdf"
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
          className="block w-full text-xs file:mr-2 file:cursor-pointer file:rounded-md file:border-0 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white"
          style={{ color: "var(--ink-muted)" }}
        />
        <style>{`input[type="file"]::file-selector-button { background-color: var(--accent); } input[type="file"]::file-selector-button:hover { background-color: var(--accent-hover); }`}</style>
        {uploading && (
          <p className="mt-2 text-xs" style={{ color: "var(--ink-muted)" }}>
            Uploading…
          </p>
        )}
        {uploadMsg && (
          <p className="mt-2 text-xs" style={{ color: "var(--ink-muted)" }}>
            {uploadMsg}
          </p>
        )}
      </section>
    </aside>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-2 text-xs font-semibold tracking-wide uppercase" style={{ color: "var(--ink-muted)" }}>
      {children}
    </h2>
  );
}

function StatTile({ value, label }: { value: number; label: string }) {
  return (
    <div
      className="rounded-xl border p-2.5 text-center"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
    >
      <div className="text-lg font-semibold tabular-nums" style={{ color: "var(--ink)" }}>
        {value}
      </div>
      <div className="text-[10px]" style={{ color: "var(--ink-muted)" }}>
        {label}
      </div>
    </div>
  );
}
