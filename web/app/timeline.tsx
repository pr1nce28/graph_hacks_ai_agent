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
  theme?: "dark" | "spiderman";
}

// Apple HIG harmonious tint palette (muted, non-neon)
const DARK_AGENT_COLORS: Record<string, string> = {
  orchestrator: "#4592FE",
  analyst: "#9D7AFF",
  action_agent: "#34C759",
  ingestion_agent: "#E5A83B",
};

// Spider-Man Light Theme agent palette
const SPIDERMAN_AGENT_COLORS: Record<string, string> = {
  orchestrator: "#1D4ED8", // Spider Royal Blue
  analyst: "#E23636", // Spider Crimson Red
  action_agent: "#059669", // Spider Green
  ingestion_agent: "#D97706", // Spider Gold
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

export function Timeline({ ticks, theme }: Props) {
  const isSpiderman = theme === "spiderman";
  const palette = isSpiderman ? SPIDERMAN_AGENT_COLORS : DARK_AGENT_COLORS;

  return (
    <div
      className="flex h-12 items-center gap-1.5 overflow-x-auto rounded-lg border p-3 transition-colors border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900/60"
      data-testid="agent-timeline"
    >
      {ticks.length === 0 && (
        <span className="text-xs text-slate-500 dark:text-slate-400">No tools called yet.</span>
      )}
      {ticks.map((t, i) => {
        const agent = inferAgent(t.tool);
        return (
          <div
            key={`tick-${i}-${t.tool}`}
            className="flex shrink-0 items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] transition-colors border-slate-200 bg-slate-50 text-slate-700 hover:border-red-300 dark:border-slate-700/60 dark:bg-slate-800/80 dark:text-slate-200 dark:hover:border-slate-600"
            title={`step ${t.step}`}
          >
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: palette[agent] ?? "#8E8E93" }}
              aria-hidden="true"
            />
            <span className="font-mono text-slate-800 dark:text-slate-200">{t.tool}</span>
          </div>
        );
      })}
    </div>
  );
}