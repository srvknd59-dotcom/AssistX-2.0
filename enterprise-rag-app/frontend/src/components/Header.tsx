import type { HealthStatus } from "../types";

interface HeaderProps {
  health: HealthStatus | null;
  healthError: boolean;
  onRebuild: () => void;
  rebuilding: boolean;
}

export function Header({ health, healthError, onRebuild, rebuilding }: HeaderProps) {
  const isReady = !!health && health.manuals_indexed > 0;

  return (
    <header className="flex items-center justify-between border-b border-black/10 bg-white px-6 py-3 dark:border-white/10 dark:bg-neutral-900">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-semibold text-white">
          RA
        </div>
        <div>
          <h1 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
            Enterprise RAG Assistant
          </h1>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            Northwind Gadgets — support &amp; documentation
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <StatusBadge healthError={healthError} isReady={isReady} />
        <button
          onClick={onRebuild}
          disabled={rebuilding}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
        >
          {rebuilding ? "Rebuilding index…" : "Rebuild index"}
        </button>
      </div>
    </header>
  );
}

function StatusBadge({ healthError, isReady }: { healthError: boolean; isReady: boolean }) {
  if (healthError) {
    return <Badge color="red" label="Backend unreachable" />;
  }
  if (!isReady) {
    return <Badge color="amber" label="Index empty — click Rebuild" />;
  }
  return <Badge color="green" label="Vector DB ready" />;
}

function Badge({ color, label }: { color: "red" | "amber" | "green"; label: string }) {
  const colors = {
    red: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    green: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  }[color];

  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${colors}`}>
      ● {label}
    </span>
  );
}
