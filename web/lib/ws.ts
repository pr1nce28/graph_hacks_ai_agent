/**
 * WebSocket client for the OrgMind chat stream.
 *
 * Connects to `/ws/chat?tenant=&session=`, sends `{question}` and emits
 * one callback per event (step / path / memory / answer / done).
 * TypeScript types mirror `docs/CONTRACTS.md` §2.
 */

export type EventType =
  | "session"
  | "step"
  | "path"
  | "memory"
  | "answer"
  | "done"
  | "error";

export interface PathEvent {
  type: "path";
  tool: string;
  path: {
    nodes: Array<{ id: string; label?: string; name?: string }>;
    edges: Array<{ source: string; target: string; type?: string }>;
  };
}

export interface StepEvent {
  type: "step";
  tool: string;
  args: Record<string, unknown>;
  step: number;
}

export interface MemoryEvent {
  type: "memory";
  op: string;
  rows?: unknown[];
}

export interface AnswerEvent {
  type: "answer";
  text: string;
  citations: string[];
  tools_called?: string[];
  dropped_citations?: string[];
}

export interface SessionEvent {
  type: "session";
  session: string;
  tenant: string;
}

export interface DoneEvent {
  type: "done";
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type OrchestratorEvent =
  | SessionEvent
  | StepEvent
  | PathEvent
  | MemoryEvent
  | AnswerEvent
  | DoneEvent
  | ErrorEvent;

export interface AskOptions {
  tenant?: string;
  session?: string;
  onEvent: (ev: OrchestratorEvent) => void;
  onError?: (msg: string) => void;
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/chat";

export function ask(
  question: string,
  opts: AskOptions,
): { cancel: () => void } {
  const params = new URLSearchParams();
  if (opts.tenant) params.set("tenant", opts.tenant);
  if (opts.session) params.set("session", opts.session);
  const url = `${WS_BASE}?${params.toString()}`;
  const ws = new WebSocket(url);

  ws.onopen = () => {
    ws.send(JSON.stringify({ question }));
  };

  ws.onmessage = (m) => {
    try {
      const ev = JSON.parse(m.data) as OrchestratorEvent;
      opts.onEvent(ev);
    } catch (e) {
      opts.onError?.(`bad event payload: ${(e as Error).message}`);
    }
  };

  ws.onerror = () => {
    opts.onError?.("websocket connection failed");
  };

  return {
    cancel: () => {
      try {
        ws.close();
      } catch {
        // ignore
      }
    },
  };
}

export interface ApiInfo {
  name: string;
  phase: number;
  tracks: string[];
}

export async function fetchInfo(): Promise<ApiInfo | null> {
  try {
    const r = await fetch(`${API_BASE}/info`, { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as ApiInfo;
  } catch {
    return null;
  }
}

/**
 * Poll `/info` until it answers, then call `onInfo`.
 *
 * The API is often still starting (or restarting) when the page loads.
 * A single failed fetch used to leave the header stuck on "phase ?" and
 * the Tracks panel empty for the life of the tab, because the effect
 * only ran once. This retries with a backoff and stops once it has an
 * answer.
 */
export function watchInfo(
  onInfo: (info: ApiInfo) => void,
  { attempts = 10, delayMs = 1500 }: { attempts?: number; delayMs?: number } = {},
): () => void {
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const tick = async (remaining: number) => {
    if (cancelled) return;
    const info = await fetchInfo();
    if (cancelled) return;
    if (info) {
      onInfo(info);
      return;
    }
    if (remaining > 0) {
      timer = setTimeout(() => void tick(remaining - 1), delayMs);
    }
  };

  void tick(attempts);
  return () => {
    cancelled = true;
    if (timer) clearTimeout(timer);
  };
}

export async function fetchTenants(): Promise<string[]> {
  try {
    const r = await fetch(`${API_BASE}/tenants`);
    if (!r.ok) return [];
    const data = (await r.json()) as { tenants: string[] };
    return data.tenants;
  } catch {
    return [];
  }
}