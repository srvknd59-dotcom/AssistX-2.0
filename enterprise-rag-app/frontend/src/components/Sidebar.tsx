import { useRef, useState } from "react";
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
    <aside className="hidden w-72 shrink-0 flex-col gap-6 border-r border-black/10 bg-white p-5 dark:border-white/10 dark:bg-neutral-900 md:flex">
      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
          Vector database
        </h2>
        <div className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
          <div className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
            {health?.chunks_indexed ?? 0}
          </div>
          <div className="text-[11px] text-neutral-500 dark:text-neutral-400">chunks indexed</div>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
          Documents ({documents.length})
        </h2>
        <ul className="space-y-1">
          {documents.map((doc) => (
            <li
              key={doc.name}
              className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
            >
              <span className="truncate">{doc.name}</span>
              <span className="ml-2 shrink-0 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-300">
                {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"}
              </span>
            </li>
          ))}
          {documents.length === 0 && (
            <li className="text-xs text-neutral-400">Not indexed yet — click "Rebuild index" above.</li>
          )}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
          Add a document
        </h2>
        <input
          ref={fileInput}
          type="file"
          accept=".txt,.md,.pdf"
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
          className="block w-full text-xs text-neutral-500 file:mr-2 file:rounded-md file:border-0 file:bg-indigo-600 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-indigo-700 dark:text-neutral-400"
        />
        {uploading && <p className="mt-2 text-xs text-neutral-400">Uploading…</p>}
        {uploadMsg && <p className="mt-2 text-xs text-neutral-500 dark:text-neutral-400">{uploadMsg}</p>}
      </section>
    </aside>
  );
}
