"use client";

/**
 * Node detail card (P4-C-03).
 * Renders the source text for a node when one is selected in the
 * GraphCanvas. The text is fetched lazily from the API (future);
 * for now we just show the node id + label as a placeholder.
 */

interface Props {
  nodeId: string | null;
  label?: string;
  name?: string;
  theme?: "dark" | "spiderman";
}

export function NodeDetail({ nodeId, label, name, theme = "dark" }: Props) {
  const isSpidey = theme === "spiderman";
  if (!nodeId) {
    return (
      <div
        className={`rounded-lg border p-4 text-sm transition-colors ${
          isSpidey
            ? "border-slate-200 bg-white/95 text-slate-500 shadow-sm"
            : "border-slate-800 bg-slate-900/60 text-slate-500"
        }`}
      >
        Click a node in the canvas to see its details.
      </div>
    );
  }
  return (
    <div
      className={`rounded-lg border p-4 text-sm transition-colors ${
        isSpidey
          ? "border-slate-200 bg-white/95 text-slate-800 shadow-sm"
          : "border-slate-800 bg-slate-900/60 text-slate-200"
      }`}
      data-testid="node-detail"
    >
      <div className="flex items-center justify-between">
        <span
          className={`font-mono text-xs font-semibold ${
            isSpidey ? "text-[#1d4ed8]" : "text-slate-300"
          }`}
        >
          {nodeId}
        </span>
        <span
          className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full ${
            isSpidey
              ? "bg-[#e23636]/10 text-[#e23636] border border-[#e23636]/20"
              : "text-slate-400"
          }`}
        >
          {label ?? "Node"}
        </span>
      </div>
      {name && (
        <div
          className={`mt-2 text-base font-semibold ${
            isSpidey ? "text-slate-900" : "text-slate-100"
          }`}
        >
          {name}
        </div>
      )}
      <p
        className={`mt-3 text-xs ${
          isSpidey ? "text-slate-600" : "text-slate-400"
        }`}
      >
        Source text for this node will appear here once the API exposes a
        <code
          className={`mx-1 rounded px-1.5 py-0.5 font-mono ${
            isSpidey
              ? "border border-slate-200 bg-slate-100 text-slate-800"
              : "bg-slate-800/80 text-slate-200"
          }`}
        >
          /node/{nodeId}
        </code>
        endpoint.
      </p>
    </div>
  );
}