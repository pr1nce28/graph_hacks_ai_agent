"use client";

/**
 * Memory inspector (P3-C-01): shows the latest memory events with
 * active Facts, Episodes and any SUPERSEDES chains.
 *
 * The data shape mirrors what the orchestrator emits via `memory`
 * events (CONTRACTS §2): each event has an `op` and a `rows` array.
 */

interface MemoryOp {
  op: string;
  ts: number;
  rows?: unknown[];
  new_fact_id?: string;
  old_fact_id?: string;
}

interface Props {
  events: MemoryOp[];
  theme?: "dark" | "spiderman";
}

export function MemoryInspector({ events, theme = "dark" }: Props) {
  const isSpidey = theme === "spiderman";
  return (
    <div
      className={`flex flex-col gap-2 rounded-lg border p-3 text-sm transition-colors ${
        isSpidey
          ? "border-slate-200 bg-white/95 text-slate-800 shadow-sm"
          : "border-slate-800 bg-slate-900/60 text-slate-200"
      }`}
      data-testid="memory-inspector"
    >
      <div className="flex items-center justify-between">
        <h3
          className={`text-xs font-semibold uppercase tracking-wider ${
            isSpidey ? "text-[#1d4ed8]" : "text-slate-400"
          }`}
        >
          Memory
        </h3>
        <span
          className={`text-[10px] font-mono ${
            isSpidey ? "text-slate-500" : "text-slate-500"
          }`}
        >
          {events.length} event{events.length === 1 ? "" : "s"}
        </span>
      </div>
      {events.length === 0 && (
        <p className={`text-xs ${isSpidey ? "text-slate-500" : "text-slate-500"}`}>
          No memory activity yet. Ask a question to start a session.
        </p>
      )}
      {events.map((e, i) => (
        <div
          key={`mem-${i}`}
          className={`rounded border p-2 transition-colors ${
            isSpidey
              ? "border-slate-200 bg-slate-50 text-slate-700"
              : "border-slate-800/80 bg-slate-950/60 text-slate-300"
          }`}
        >
          <div
            className={`flex items-center justify-between text-[10px] ${
              isSpidey ? "text-slate-500" : "text-slate-400"
            }`}
          >
            <span
              className={`font-mono font-medium ${
                isSpidey ? "text-[#e23636]" : "text-slate-300"
              }`}
            >
              {e.op}
            </span>
            <span>{new Date(e.ts).toLocaleTimeString()}</span>
          </div>
          {e.old_fact_id && e.new_fact_id && (
            <div
              className={`mt-1 text-[11px] font-medium ${
                isSpidey ? "text-amber-700 font-mono" : "text-amber-300/80"
              }`}
            >
              {e.old_fact_id} → {e.new_fact_id} (SUPERSEDES)
            </div>
          )}
        </div>
      ))}
    </div>
  );
}