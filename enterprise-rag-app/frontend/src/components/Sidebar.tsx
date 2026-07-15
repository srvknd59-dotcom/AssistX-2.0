import { FileText, Inbox, UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent, type ReactNode } from "react";
import { uploadDocument } from "../api/client";
import type { DocumentInfo } from "../types";

interface SidebarProps {
  documents: DocumentInfo[];
  onUploaded: () => void;
}

export function Sidebar({ documents, onUploaded }: SidebarProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = async (file: File) => {
    setUploading(true);
    setUploadMsg(null);
    try {
      await uploadDocument(file);
      setUploadMsg(`"${file.name}" added. Click "Sync documents" above to include it.`);
      onUploaded();
    } catch {
      setUploadMsg(`Couldn't add "${file.name}". Supported types: .txt, .md, .pdf`);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <aside
      className="hidden w-80 shrink-0 flex-col gap-6 overflow-y-auto p-5 md:flex"
      style={{ backgroundColor: "var(--surface-2)" }}
    >
      <section>
        <SectionLabel>Add a document</SectionLabel>
        <div
          onClick={() => !uploading && fileInput.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          className="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-4 py-7 text-center transition-all"
          style={{
            borderColor: isDragging ? "var(--accent)" : "var(--border)",
            backgroundColor: isDragging ? "var(--accent-soft)" : "var(--surface)",
            boxShadow: isDragging ? "var(--shadow-md)" : "none",
          }}
        >
          <div
            className="flex h-11 w-11 items-center justify-center rounded-full"
            style={{ backgroundColor: "var(--accent-soft)" }}
          >
            <UploadCloud className="h-5 w-5" style={{ color: "var(--accent)" }} strokeWidth={2} />
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--ink)" }}>
              Drop a file, or click to browse
            </p>
            <p className="mt-0.5 text-xs" style={{ color: "var(--ink-muted)" }}>
              .txt, .md, .pdf — tables and images included
            </p>
          </div>
          <input
            ref={fileInput}
            type="file"
            accept=".txt,.md,.pdf"
            disabled={uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
            }}
            className="hidden"
          />
        </div>
        {uploading && (
          <p className="mt-2 text-xs font-medium" style={{ color: "var(--accent)" }}>
            Uploading…
          </p>
        )}
        {uploadMsg && (
          <p className="mt-2 text-xs" style={{ color: "var(--ink-muted)" }}>
            {uploadMsg}
          </p>
        )}
      </section>

      <section className="flex min-h-0 flex-1 flex-col">
        <SectionLabel>Documents ({documents.length})</SectionLabel>
        {documents.length === 0 ? (
          <div
            className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border py-8 text-center"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <Inbox className="h-6 w-6" style={{ color: "var(--ink-muted)" }} strokeWidth={1.75} />
            <p className="max-w-[16ch] text-xs" style={{ color: "var(--ink-muted)" }}>
              No documents yet — add one above
            </p>
          </div>
        ) : (
          <ul className="space-y-1">
            {documents.map((doc) => (
              <li
                key={doc.name}
                className="flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm transition-colors hover:bg-black/[0.03] dark:hover:bg-white/[0.06]"
                style={{ color: "var(--ink)" }}
              >
                <FileIcon name={doc.name} />
                <span className="min-w-0 flex-1 truncate">{doc.name}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}

function FileIcon({ name }: { name: string }) {
  const isPdf = name.toLowerCase().endsWith(".pdf");
  return (
    <div
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
      style={{ backgroundColor: isPdf ? "var(--file-pdf-soft)" : "var(--file-doc-soft)" }}
    >
      <FileText className="h-4 w-4" style={{ color: isPdf ? "var(--file-pdf)" : "var(--file-doc)" }} strokeWidth={2} />
    </div>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-2.5 text-xs font-semibold tracking-wide uppercase" style={{ color: "var(--ink-muted)" }}>
      {children}
    </h2>
  );
}
