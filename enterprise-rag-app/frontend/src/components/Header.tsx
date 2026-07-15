import { RefreshCw, Sparkles } from "lucide-react";
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
      className="flex items-center justify-between px-6 py-3.5"
      style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow-sm)" }}
    >
      <div className="flex items-center gap-3">
        <div
          className="brand-mark flex h-9 w-9 items-center justify-center rounded-xl text-white"
          style={{ boxShadow: "var(--shadow-md)" }}
        >
          <Sparkles className="h-4.5 w-4.5" strokeWidth={2.25} />
        </div>
        <div>
          <h1 className="text-[15px] font-semibold tracking-tight" style={{ color: "var(--ink)" }}>
            Document Assistant
          </h1>
          <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
            Ask questions, grounded in your documents
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <StatusBadge healthError={healthError} isReady={isReady} />
        <button
          onClick={onRebuild}
          disabled={rebuilding}
          className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50"
          style={{ borderColor: "var(--border)", color: "var(--ink)", backgroundColor: "var(--surface)" }}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${rebuilding ? "animate-spin" : ""}`} strokeWidth={2.25} />
          {rebuilding ? "Syncing…" : "Sync documents"}
        </button>
      </div>
    </header>
  );
}

function StatusBadge({ healthError, isReady }: { healthError: boolean; isReady: boolean }) {
  if (healthError) {
    return <Badge tone="critical" label="Can't connect" />;
  }
  if (!isReady) {
    return <Badge tone="warn" label="No documents yet" />;
  }
  return <Badge tone="good" label="Ready" />;
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
