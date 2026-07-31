import type { ReactNode } from "react";

export function TerminalPageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-slate-800 pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && (
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {eyebrow}
          </div>
        )}
        <h2 className="text-2xl font-semibold tracking-tight text-slate-50">{title}</h2>
        <p className="mt-1 text-sm text-slate-400">{description}</p>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

export function RefreshButton({
  loading,
  onClick,
  label = "Refresh",
}: {
  loading: boolean;
  onClick: () => void;
  label?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="inline-flex items-center gap-2 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-200 transition-colors hover:border-slate-600 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className={loading ? "inline-block animate-spin" : "inline-block"} aria-hidden="true">↻</span>
      {loading ? "Refreshing…" : label}
    </button>
  );
}

export function TerminalState({
  kind,
  title,
  detail,
  onRetry,
  compact = false,
}: {
  kind: "loading" | "error" | "empty";
  title: string;
  detail?: string;
  onRetry?: () => void;
  compact?: boolean;
}) {
  const styles = {
    loading: "border-slate-800 bg-slate-900/50 text-slate-300",
    error: "border-red-800/80 bg-red-950/30 text-red-200",
    empty: "border-slate-800 bg-slate-900/50 text-slate-300",
  };
  const icon = kind === "loading" ? "◌" : kind === "error" ? "!" : "—";

  return (
    <section
      className={`flex flex-col items-center justify-center rounded-lg border px-6 text-center ${
        compact ? "min-h-32 py-6" : "min-h-64 py-10"
      } ${styles[kind]}`}
      role={kind === "error" ? "alert" : undefined}
    >
      <span
        className={`mb-3 flex h-9 w-9 items-center justify-center rounded-full border border-current/20 text-lg font-semibold ${
          kind === "loading" ? "animate-spin" : ""
        }`}
        aria-hidden="true"
      >
        {icon}
      </span>
      <h3 className="text-sm font-semibold text-inherit">{title}</h3>
      {detail && <p className="mt-1 max-w-md text-sm text-slate-400">{detail}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-md border border-red-700 bg-red-950/60 px-3 py-2 text-sm font-medium text-red-200 transition-colors hover:bg-red-900/60"
        >
          Retry connection
        </button>
      )}
    </section>
  );
}

export function NoticeBanner({
  children,
  tone = "warning",
}: {
  children: ReactNode;
  tone?: "warning" | "error" | "info";
}) {
  const styles = {
    warning: "border-amber-800/80 bg-amber-950/30 text-amber-200",
    error: "border-red-800/80 bg-red-950/30 text-red-200",
    info: "border-blue-800/80 bg-blue-950/30 text-blue-200",
  };
  return (
    <div className={`rounded-md border px-4 py-3 text-sm ${styles[tone]}`} role={tone === "error" ? "alert" : undefined}>
      {children}
    </div>
  );
}

export function StatusPill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  const styles = {
    neutral: "border-slate-700 bg-slate-800 text-slate-300",
    success: "border-emerald-800 bg-emerald-950/50 text-emerald-300",
    warning: "border-amber-800 bg-amber-950/50 text-amber-300",
    danger: "border-red-800 bg-red-950/50 text-red-300",
  };
  return <span className={`inline-flex items-center rounded border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${styles[tone]}`}>{children}</span>;
}
