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
}

export function NodeDetail({ nodeId, label, name }: Props) {
  if (!nodeId) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-500">
        Click a node in the canvas to see its details.
      </div>
    );
  }
  return (
    <div
      className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-200"
      data-testid="node-detail"
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-slate-400">{nodeId}</span>
        <span className="text-[10px] uppercase tracking-wider text-slate-500">
          {label ?? "Node"}
        </span>
      </div>
      {name && <div className="mt-2 text-base">{name}</div>}
      <p className="mt-3 text-xs text-slate-400">
        Source text for this node will appear here once the API exposes a
        <code className="mx-1 rounded bg-slate-800 px-1">/node/{nodeId}</code>
        endpoint.
      </p>
    </div>
  );
}