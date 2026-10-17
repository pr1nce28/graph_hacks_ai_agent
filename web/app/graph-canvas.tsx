"use client";

/**
 * SVG-based graph canvas.
 *
 * - Nodes are coloured by label (P4-C-02).
 * - Edges show their type on hover (P4-C-02).
 * - The path events from the orchestrator light nodes up in arrival
 *   order (P4-C-01) — each new arrival gets a 2s pulse.
 * - Clicking a node raises `onSelect` so the parent can show a detail
 *   card (P4-C-03).
 */

import { useEffect, useMemo, useRef, useState } from "react";

interface Node {
  id: string;
  label?: string;
  name?: string;
  x?: number;
  y?: number;
  // visualisation-only state
  arrived?: number;
  selected?: boolean;
}

interface Edge {
  source: string;
  target: string;
  type?: string;
}

interface PathPayload {
  nodes: Node[];
  edges: Edge[];
}

interface Props {
  paths: PathPayload[];
  onSelect?: (id: string) => void;
  selectedId?: string | null;
}

// Colour by label — slate/blue/emerald/amber/rose/fuchsia palette.
const LABEL_COLORS: Record<string, string> = {
  Person: "#60a5fa",
  Team: "#a78bfa",
  Project: "#f472b6",
  Service: "#34d399",
  Document: "#fbbf24",
  Ticket: "#fb7185",
  Message: "#22d3ee",
  Decision: "#c084fc",
  Fact: "#facc15",
  Episode: "#4ade80",
  Procedure: "#2dd4bf",
  Agent: "#e879f9",
  Task: "#fda4af",
  Handoff: "#fdba74",
};

const FALLBACK_COLOR = "#94a3b8";

function colorFor(label?: string): string {
  if (!label) return FALLBACK_COLOR;
  return LABEL_COLORS[label] ?? FALLBACK_COLOR;
}

function layoutNodes(paths: PathPayload[]): {
  nodes: Map<string, Node>;
  edges: Edge[];
} {
  const nodes = new Map<string, Node>();
  const edges: Edge[] = [];
  for (const p of paths) {
    for (const n of p.nodes) {
      if (!nodes.has(n.id)) {
        nodes.set(n.id, { ...n });
      }
    }
    for (const e of p.edges) {
      edges.push(e);
    }
  }
  // Simple grid layout: spread nodes in a circle of radius 130 centred
  // on (200, 200). Real graphs use force layouts; this is good enough
  // for the demo because we typically have < 30 nodes.
  const arr = Array.from(nodes.values());
  const cx = 200;
  const cy = 200;
  const r = 130;
  arr.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(arr.length, 1);
    n.x = cx + r * Math.cos(angle);
    n.y = cy + r * Math.sin(angle);
  });
  return { nodes, edges };
}

export function GraphCanvas({ paths, onSelect, selectedId }: Props) {
  const [hoveredEdge, setHoveredEdge] = useState<Edge | null>(null);
  const [pulseTick, setPulseTick] = useState(0);

  const { nodes, edges } = useMemo(() => layoutNodes(paths), [paths]);

  // Track each node's arrival timestamp so we can animate its colour
  // pulse for 2s after a path event arrives.
  const arrivalRef = useRef<Map<string, number>>(new Map());
  useEffect(() => {
    const now = Date.now();
    for (const p of paths) {
      for (const n of p.nodes) {
        const prev = arrivalRef.current.get(n.id) ?? 0;
        if (now - prev > 100) {
          // Mark as arrived NOW so the pulse starts.
          arrivalRef.current.set(n.id, now);
        }
      }
    }
    // Force a tick to re-render so the new pulse starts.
    setPulseTick((t) => t + 1);
    const t = window.setTimeout(() => setPulseTick((x) => x + 1), 2000);
    return () => window.clearTimeout(t);
  }, [paths]);

  return (
    <svg
      role="img"
      aria-label="Graph canvas"
      viewBox="0 0 400 400"
      className="h-full w-full bg-slate-950"
      data-pulse-tick={pulseTick}
    >
      {/* edges */}
      <g aria-label="edges">
        {edges.map((e, i) => {
          const a = nodes.get(e.source);
          const b = nodes.get(e.target);
          if (!a || !b || a.x == null || b.x == null || a.y == null || b.y == null) return null;
          const isHovered =
            hoveredEdge &&
            hoveredEdge.source === e.source &&
            hoveredEdge.target === e.target;
          return (
            <g key={`edge-${i}`}>
              <line
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={isHovered ? "#fbbf24" : "#475569"}
                strokeWidth={isHovered ? 2 : 1}
                onMouseEnter={() => setHoveredEdge(e)}
                onMouseLeave={() => setHoveredEdge(null)}
              />
              {isHovered && (
                <text
                  x={(a.x + b.x) / 2}
                  y={(a.y + b.y) / 2 - 4}
                  textAnchor="middle"
                  fill="#fbbf24"
                  fontSize={10}
                >
                  {e.type ?? "?"}
                </text>
              )}
            </g>
          );
        })}
      </g>
      {/* nodes */}
      <g aria-label="nodes">
        {Array.from(nodes.values()).map((n) => {
          const arrived = arrivalRef.current.get(n.id) ?? 0;
          const since = Date.now() - arrived;
          const pulse = since < 2000;
          const r = pulse ? 12 + 6 * (1 - since / 2000) : 12;
          const fill = colorFor(n.label);
          const stroke = selectedId === n.id ? "#fff" : "#0f172a";
          return (
            <g
              key={n.id}
              transform={`translate(${n.x ?? 0},${n.y ?? 0})`}
              onClick={() => onSelect?.(n.id)}
              style={{ cursor: "pointer" }}
            >
              <circle
                r={r}
                fill={fill}
                stroke={stroke}
                strokeWidth={selectedId === n.id ? 2 : 1}
              />
              <text
                y={r + 12}
                textAnchor="middle"
                fill="#cbd5e1"
                fontSize={9}
              >
                {n.id}
              </text>
            </g>
          );
        })}
      </g>
      {/* hover tooltip for edge labels */}
      {hoveredEdge && (
        <g transform="translate(8,392)">
          <text fill="#94a3b8" fontSize={10}>
            edge: {hoveredEdge.source} → {hoveredEdge.target}
          </text>
        </g>
      )}
    </svg>
  );
}