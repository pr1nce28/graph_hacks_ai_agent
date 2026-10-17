"use client";

/**
 * Agent timeline strip (P4-C-04).
 * Shows a horizontal sequence of Orchestrator → Analyst / Action /
 * Ingestion ticks as the orchestrator emits step events. Each tick
 * shows the agent that ran and the tool name.
 */

interface Tick {
  agent: string;
  tool: string;
  step: number;
  ts: number;
}

interface Props {
  ticks: Tick[];
}

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "#60a5fa",
  analyst: "#a78bfa",
  action_agent: "#34d399",
  ingestion_agent: "#fbbf24",
};

function inferAgent(tool: string): string {
  if (tool.startsWith("create_") || tool.startsWith("draft_") || tool === "update_task") {
    return "action_agent";
  }
  if (tool.startsWith("remember") || tool.startsWith("recall") || tool.startsWith("supersede")) {
    return "orchestrator";
  }
  return "analyst";
}

export function Timeline({ ticks }: Props) {
  return (
    <div
      className="flex h-12 items-center gap-1 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/60 px-3"
      data-testid="agent-timeline"
    >
      {ticks.length === 0 && (
        <span className="text-xs text-slate-500">No tools called yet.</span>
      )}
      {ticks.map((t, i) => {
        const agent = inferAgent(t.tool);
        return (
          <div
            key={`tick-${i}-${t.tool}`}
            className="flex shrink-0 items-center gap-1 rounded-md border border-slate-700 bg-slate-800/80 px-2 py-1 text-[10px]"
            title={`step ${t.step}`}
          >
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: AGENT_COLORS[agent] ?? "#94a3b8" }}
              aria-hidden="true"
            />
            <span className="font-mono text-slate-200">{t.tool}</span>
          </div>
        );
      })}
    </div>
  );
}