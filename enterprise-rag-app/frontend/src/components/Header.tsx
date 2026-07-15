import type { HealthStatus } from "../types";

interface HeaderProps {
  health: HealthStatus | null;
  healthError: boolean;
  onRebuild: () => void;
  rebuilding: boolean;
}

export function Header({ health, healthError, onRebuild, rebuilding }: HeaderProps) {
  const isReady = !!health && health.chunks_indexed > 0;

  return (
    <header
      className="flex items-center justify-between border-b px-6 py-3.5"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <div className="flex items-center gap-3">
        <div
          className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-semibold text-white shadow-sm"
          style={{ backgroundColor: "var(--accent)" }}
        >
          RA
        </div>
        <div>
          <h1 className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
            Document Search Assistant
          </h1>
          <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
            RAG over your ingested documents
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <StatusBadge healthError={healthError} isReady={isReady} />
        <button
          onClick={onRebuild}
          disabled={rebuilding}
          className="rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
          style={{ borderColor: "var(--border)", color: "var(--ink)", backgroundColor: "var(--surface)" }}
        >
          {rebuilding ? "Rebuilding index…" : "Rebuild index"}
        </button>
      </div>
    </header>
  );
}

function StatusBadge({ healthError, isReady }: { healthError: boolean; isReady: boolean }) {
  if (healthError) {
    return <Badge tone="critical" label="Backend unreachable" />;
  }
  if (!isReady) {
    return <Badge tone="warn" label="Index empty — click Rebuild" />;
  }
  return <Badge tone="good" label="Vector DB ready" />;
}

function Badge({ tone, label }: { tone: "critical" | "warn" | "good"; label: string }) {
  return (
    <span
      className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
      style={{ backgroundColor: `var(--${tone}-soft)`, color: `var(--${tone})` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: `var(--${tone})` }} />
      {label}
    </span>
  );
}
