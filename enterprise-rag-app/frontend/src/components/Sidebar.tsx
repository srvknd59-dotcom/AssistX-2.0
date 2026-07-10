import type { DocumentInfo, HealthStatus } from "../types";

interface SidebarProps {
  health: HealthStatus | null;
  documents: DocumentInfo[];
}

export function Sidebar({ health, documents }: SidebarProps) {
  const manuals = documents.filter((d) => d.type === "manual");
  const tickets = documents.filter((d) => d.type === "ticket");

  return (
    <aside className="hidden w-72 shrink-0 flex-col gap-6 border-r border-black/10 bg-white p-5 dark:border-white/10 dark:bg-neutral-900 md:flex">
      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
          Vector database
        </h2>
        <div className="grid grid-cols-2 gap-2">
          <Stat label="Manual chunks" value={health?.manuals_indexed ?? 0} />
          <Stat label="Ticket entries" value={health?.tickets_indexed ?? 0} />
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
          Manuals ({manuals.length})
        </h2>
        <ul className="space-y-1">
          {manuals.map((doc) => (
            <li
              key={doc.name}
              className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
            >
              <span className="truncate">{doc.name}</span>
              <span className="ml-2 shrink-0 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-300">
                {doc.chunk_count} chunks
              </span>
            </li>
          ))}
          {manuals.length === 0 && <EmptyHint />}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
          Support tickets ({tickets.reduce((n, t) => n + t.chunk_count, 0)})
        </h2>
        <ul className="space-y-1">
          {tickets.map((doc) => (
            <li
              key={doc.name}
              className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm text-neutral-700 dark:text-neutral-300"
            >
              <span className="truncate">{doc.name}</span>
              <span className="ml-2 shrink-0 rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-medium text-teal-600 dark:bg-teal-900/40 dark:text-teal-300">
                {doc.chunk_count}
              </span>
            </li>
          ))}
          {tickets.length === 0 && <EmptyHint />}
        </ul>
      </section>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
      <div className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{value}</div>
      <div className="text-[11px] text-neutral-500 dark:text-neutral-400">{label}</div>
    </div>
  );
}

function EmptyHint() {
  return <li className="text-xs text-neutral-400">Not indexed yet — click "Rebuild index" above.</li>;
}
