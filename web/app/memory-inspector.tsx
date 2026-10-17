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
}

export function MemoryInspector({ events }: Props) {
  return (
    <div
      className="flex flex-col gap-2 rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-sm"
      data-testid="memory-inspector"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Memory
        </h3>
        <span className="text-[10px] text-slate-500">
          {events.length} event{events.length === 1 ? "" : "s"}
        </span>
      </div>
      {events.length === 0 && (
        <p className="text-xs text-slate-500">
          No memory activity yet. Ask a question to start a session.
        </p>
      )}
      {events.map((e, i) => (
        <div
          key={`mem-${i}`}
          className="rounded border border-slate-800 bg-slate-950/60 p-2"
        >
          <div className="flex items-center justify-between text-[10px] text-slate-500">
            <span className="font-mono">{e.op}</span>
            <span>{new Date(e.ts).toLocaleTimeString()}</span>
          </div>
          {e.old_fact_id && e.new_fact_id && (
            <div className="mt-1 text-[11px] text-amber-300">
              {e.old_fact_id} → {e.new_fact_id} (SUPERSEDES)
            </div>
          )}
        </div>
      ))}
    </div>
  );
}