"use client";

/**
 * SVG-based graph canvas with Apple HIG color palette.
 *
 * - Nodes are coloured by label using refined Apple HIG system tints (P4-C-02).
 * - Edges show their type on hover (P4-C-02).
 * - Newly arrived nodes receive a gentle subtle pulse (P4-C-01).
 * - Clicking a node raises `onSelect` for the detail card (P4-C-03).
 */

import { useEffect, useMemo, useRef, useState } from "react";

interface Node {
  id: string;
  label?: string;
  name?: string;
  x?: number;
  y?: number;
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
  theme?: "dark" | "spiderman";
}

// Apple Dark palette - Restrained, cohesive system tints
const DARK_LABEL_COLORS: Record<string, string> = {
  Person: "#4592FE",
  Team: "#9D7AFF",
  Project: "#F06292",
  Service: "#34C759",
  Document: "#E5A83B",
  Ticket: "#FF6961",
  Message: "#5AC8FA",
  Decision: "#AF52DE",
  Fact: "#FFCC00",
  Episode: "#30D158",
  Procedure: "#30B0C7",
  Agent: "#D170D8",
  Task: "#FF9500",
  Handoff: "#A2845E",
};

// Spider-Man Light Theme Palette
const SPIDERMAN_LABEL_COLORS: Record<string, string> = {
  Person: "#E23636", // Spidey Crimson Red
  Team: "#1D4ED8", // Spider Royal Blue
  Project: "#0F172A", // Symbiote Black Suit
  Service: "#0284C7", // Sky Web Blue
  Document: "#D97706", // Spider Gold
  Ticket: "#DC2626", // Crimson Ticket
  Message: "#2563EB", // Web Blue
  Decision: "#7C3AED", // Spider Purple
  Fact: "#B45309", // Amber Fact
  Episode: "#059669", // Spider Green
  Procedure: "#0D9488", // Web Teal
  Agent: "#DB2777", // Spider-Gwen Pink
  Task: "#EA580C", // Spidey Orange
  Handoff: "#64748B", // Web Silver
};

const FALLBACK_COLOR = "#8E8E93";

function colorFor(label?: string, theme: "dark" | "spiderman" = "dark"): string {
  if (!label) return FALLBACK_COLOR;
  const palette = theme === "spiderman" ? SPIDERMAN_LABEL_COLORS : DARK_LABEL_COLORS;
  return palette[label] ?? FALLBACK_COLOR;
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

export function GraphCanvas({ paths, onSelect, selectedId, theme }: Props) {
  const [hoveredEdge, setHoveredEdge] = useState<Edge | null>(null);
  const [pulseTick, setPulseTick] = useState(0);

  const { nodes, edges } = useMemo(() => layoutNodes(paths), [paths]);
  const isSpiderman = theme === "spiderman";

  const arrivalRef = useRef<Map<string, number>>(new Map());
  useEffect(() => {
    const now = Date.now();
    for (const p of paths) {
      for (const n of p.nodes) {
        const prev = arrivalRef.current.get(n.id) ?? 0;
        if (now - prev > 100) {
          arrivalRef.current.set(n.id, now);
        }
      }
    }
    setPulseTick((t) => t + 1);
    const t = window.setTimeout(() => setPulseTick((x) => x + 1), 2000);
    return () => window.clearTimeout(t);
  }, [paths]);

  const edgeNormalColor = isSpiderman ? "#cbd5e1" : "#334155";
  const edgeHoverColor = isSpiderman ? "#e23636" : "#0071e3";
  const edgeTextColor = isSpiderman ? "#e23636" : "#94a3b8";

  return (
    <svg
      role="img"
      aria-label="Graph canvas"
      viewBox="0 0 400 400"
      className="h-full w-full rounded-lg border select-none transition-colors border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"
      data-pulse-tick={pulseTick}
    >
      <defs>
        {isSpiderman && (
          <pattern
            id="spidey-web-grid"
            width="40"
            height="40"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 40 0 L 0 40 M 0 0 L 40 40"
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="0.5"
              opacity="0.6"
            />
          </pattern>
        )}
      </defs>

      {isSpiderman && <rect width="400" height="400" fill="url(#spidey-web-grid)" />}

      {/* edges */}
      <g aria-label="edges">
        {edges.map((e, i) => {
          const a = nodes.get(e.source);
          const b = nodes.get(e.target);
          if (
            !a ||
            !b ||
            a.x == null ||
            b.x == null ||
            a.y == null ||
            b.y == null
          ) {
            return null;
          }
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
                stroke={isHovered ? edgeHoverColor : edgeNormalColor}
                strokeWidth={isHovered ? 2 : 1.2}
                className="cursor-pointer transition-colors duration-150"
                onMouseEnter={() => setHoveredEdge(e)}
                onMouseLeave={() => setHoveredEdge(null)}
              />
              {isHovered && (
                <text
                  x={(a.x + b.x) / 2}
                  y={(a.y + b.y) / 2 - 4}
                  textAnchor="middle"
                  fill={edgeTextColor}
                  fontSize={10}
                  fontWeight="600"
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
          const fill = colorFor(n.label, theme);
          const isSelected = selectedId === n.id;
          const stroke = isSelected
            ? isSpiderman
              ? "#e23636"
              : "#ffffff"
            : pulse
              ? fill
              : isSpiderman
                ? "#ffffff"
                : "#0f172a";

          return (
            <g
              key={n.id}
              transform={`translate(${n.x ?? 0},${n.y ?? 0})`}
              onClick={() => onSelect?.(n.id)}
              className="cursor-pointer transition-transform hover:scale-105"
            >
              {isSelected && (
                <circle
                  r={16}
                  fill="none"
                  stroke={isSpiderman ? "#e23636" : "#0071e3"}
                  strokeWidth={2}
                  opacity={0.85}
                />
              )}
              <circle
                r={12}
                fill={fill}
                stroke={stroke}
                strokeWidth={isSelected ? 2 : 1.5}
              />
              <text
                y={22}
                textAnchor="middle"
                fill={
                  isSelected
                    ? isSpiderman
                      ? "#e23636"
                      : "#f8fafc"
                    : isSpiderman
                      ? "#334155"
                      : "#94a3b8"
                }
                fontSize={9}
                fontWeight={isSelected ? "600" : "500"}
              >
                {n.id}
              </text>
            </g>
          );
        })}
      </g>
      {/* hover tooltip for edge labels */}
      {hoveredEdge && (
        <g transform="translate(10,388)">
          <text fill={edgeTextColor} fontSize={11} fontWeight={isSpiderman ? "500" : "400"}>
            edge: {hoveredEdge.source} → {hoveredEdge.target}
          </text>
        </g>
      )}
    </svg>
  );
}