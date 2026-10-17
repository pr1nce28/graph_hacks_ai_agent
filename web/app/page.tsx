"use client";

/**
 * Main OrgMind chat page.
 *
 * Wires the chat panel, the live graph canvas, the agent timeline and
 * the memory inspector. Streams orchestrator events over WebSocket.
 *
 * Tracks covered (P4-C-01..06):
 *   - P4-C-01: nodes pulse as path events stream in (graph-canvas.tsx)
 *   - P4-C-02: nodes coloured by label (graph-canvas.tsx)
 *   - P4-C-03: node detail card on selection
 *   - P4-C-04: agent timeline strip
 *   - P4-C-05: loading + error states in Chat
 *   - P4-C-06: dark theme + synthetic-data banner
 */

import { useEffect, useMemo, useState } from "react";

import { Chat } from "./chat";
import { GraphCanvas } from "./graph-canvas";
import { MemoryInspector } from "./memory-inspector";
import { NodeDetail } from "./node-detail";
import { Timeline } from "./timeline";
import {
  ask,
  fetchInfo,
  fetchTenants,
  type OrchestratorEvent,
  type PathEvent,
} from "../lib/ws";

interface Message {
  role: "user" | "assistant";
  text: string;
  citations: string[];
  dropped: string[];
}

interface Tick {
  agent: string;
  tool: string;
  step: number;
  ts: number;
}

interface MemoryOp {
  op: string;
  ts: number;
  rows?: unknown[];
  new_fact_id?: string;
  old_fact_id?: string;
}

export default function HomePage() {
  const [info, setInfo] = useState<{
    name: string;
    phase: number;
    tracks: string[];
  } | null>(null);
  const [tenants, setTenants] = useState<string[]>([]);
  const [tenant, setTenant] = useState<string>("org_acme");
  const [messages, setMessages] = useState<Message[]>([]);
  const [paths, setPaths] = useState<PathEvent[]>([]);
  const [ticks, setTicks] = useState<Tick[]>([]);
  const [memory, setMemory] = useState<MemoryOp[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    void fetchInfo().then(setInfo);
    void fetchTenants().then((ts) => {
      setTenants(ts);
      if (ts.length && !ts.includes(tenant)) setTenant(ts[0]);
    });
  }, [tenant]);

  const handleSend = (q: string) => {
    setPending(true);
    setError(null);
    setMessages((m) => [...m, { role: "user", text: q, citations: [], dropped: [] }]);

    ask(q, {
      tenant,
      onEvent: (ev: OrchestratorEvent) => {
        switch (ev.type) {
          case "step":
            setTicks((arr) => [
              ...arr,
              {
                agent: "analyst",
                tool: ev.tool,
                step: ev.step,
                ts: Date.now(),
              },
            ]);
            break;
          case "path":
            setPaths((arr) => [...arr, ev]);
            break;
          case "memory":
            setMemory((arr) => [
              ...arr,
              {
                op: (ev as unknown as { op: string }).op ?? "memory",
                ts: Date.now(),
                ...(ev as unknown as { rows?: unknown[] }),
              },
            ]);
            break;
          case "answer":
            setMessages((m) => [
              ...m,
              {
                role: "assistant",
                text: ev.text,
                citations: ev.citations ?? [],
                dropped: ev.dropped_citations ?? [],
              },
            ]);
            break;
          case "done":
            setPending(false);
            break;
          case "error":
            setError(ev.message);
            setPending(false);
            break;
          default:
            break;
        }
      },
      onError: (m) => {
        setError(m);
        setPending(false);
      },
    });
  };

  const flatPaths = useMemo(
    () =>
      paths.map((p) => ({
        nodes: p.path.nodes,
        edges: p.path.edges,
      })),
    [paths],
  );

  const selectedNode = useMemo(() => {
    if (!selectedId) return null;
    for (const p of paths) {
      const n = p.path.nodes.find((x) => x.id === selectedId);
      if (n) return n;
    }
    return null;
  }, [paths, selectedId]);

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-4 px-6 py-4">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-50">
            OrgMind
          </h1>
          <p className="text-sm text-slate-400">
            Company Brain · FalkorDB · {info ? `phase ${info.phase}` : "phase ?"}
          </p>
        </div>
        <div
          className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-[11px] text-amber-300"
          data-testid="synthetic-banner"
        >
          Synthetic demo data only — no real company information is stored.
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_2fr_1fr]">
        <div className="flex flex-col gap-3">
          <Chat
            messages={messages}
            pending={pending}
            error={error}
            onSend={handleSend}
            onCitationClick={setSelectedId}
          />
          <Timeline ticks={ticks} />
        </div>

        <div className="flex h-[60vh] flex-col gap-3 lg:h-[70vh]">
          <GraphCanvas
            paths={flatPaths}
            onSelect={setSelectedId}
            selectedId={selectedId}
          />
          <NodeDetail
            nodeId={selectedId}
            label={selectedNode?.label}
            name={selectedNode?.name}
          />
        </div>

        <aside className="flex flex-col gap-3">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-sm">
            <label className="block text-xs uppercase tracking-wider text-slate-400">
              Tenant
            </label>
            <select
              value={tenant}
              onChange={(e) => setTenant(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
              data-testid="tenant-select"
            >
              {tenants.length === 0 && <option value={tenant}>{tenant}</option>}
              {tenants.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <MemoryInspector events={memory} />
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-400">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Tracks
            </h3>
            <ul className="mt-2 space-y-1">
              {(info?.tracks ?? []).map((t) => (
                <li key={t} className="rounded bg-slate-950/60 px-2 py-1">
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </section>
    </main>
  );
}