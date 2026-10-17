"use client";

/**
 * Chat panel.
 * - Input box with submit (Enter to send).
 * - Streamed assistant answer with clickable citations.
 * - Loading and error states (P4-C-05).
 */

import { useState } from "react";

interface Message {
  role: "user" | "assistant";
  text: string;
  citations?: string[];
  dropped?: string[];
}

interface Props {
  messages: Message[];
  pending: boolean;
  error: string | null;
  onSend: (q: string) => void;
  onCitationClick?: (id: string) => void;
}

export function Chat({
  messages,
  pending,
  error,
  onSend,
  onCitationClick,
}: Props) {
  const [draft, setDraft] = useState("");
  return (
    <div
      className="flex h-full flex-col gap-3 rounded-lg border border-slate-800 bg-slate-900/60 p-3"
      data-testid="chat-panel"
    >
      <div className="flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="text-sm text-slate-500">
            Ask anything about the company. The agent walks the graph and
            cites the nodes it touched.
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={`msg-${i}`}
            className={
              "rounded-lg border p-2 text-sm " +
              (m.role === "user"
                ? "border-sky-700 bg-sky-950/40 text-sky-100"
                : "border-slate-700 bg-slate-950/40 text-slate-100")
            }
          >
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              {m.role}
            </div>
            <div className="mt-1 whitespace-pre-wrap leading-relaxed">
              {renderCitations(m.text, m.citations ?? [], onCitationClick)}
            </div>
            {m.citations && m.citations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {m.citations.map((c) => (
                  <button
                    key={c}
                    onClick={() => onCitationClick?.(c)}
                    className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300 hover:bg-slate-700"
                    title={`Focus ${c}`}
                  >
                    [{c}]
                  </button>
                ))}
              </div>
            )}
            {m.dropped && m.dropped.length > 0 && (
              <div className="mt-1 text-[10px] text-amber-400">
                dropped: {m.dropped.join(", ")}
              </div>
            )}
          </div>
        ))}
        {pending && (
          <div
            className="rounded-lg border border-slate-700 bg-slate-950/40 p-2 text-sm text-slate-400"
            data-testid="chat-loading"
          >
            Thinking… the agent is reasoning over the graph.
          </div>
        )}
        {error && (
          <div
            className="rounded-lg border border-rose-700 bg-rose-950/40 p-2 text-sm text-rose-200"
            data-testid="chat-error"
          >
            {error}
          </div>
        )}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const q = draft.trim();
          if (!q || pending) return;
          setDraft("");
          onSend(q);
        }}
        className="flex gap-2"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask the Company Brain…"
          className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none"
          data-testid="chat-input"
        />
        <button
          type="submit"
          disabled={pending || !draft.trim()}
          className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:bg-slate-700"
          data-testid="chat-send"
        >
          Send
        </button>
      </form>
    </div>
  );
}

function renderCitations(
  text: string,
  citations: string[],
  onClick?: (id: string) => void,
): React.ReactNode {
  // Replace [node_id] with a clickable button if the id is in the
  // citation set; otherwise render the literal text so the user sees
  // that the orchestrator dropped that id.
  const parts = text.split(/(\[[A-Za-z_][\w]*\])/g);
  return parts.map((part, i) => {
    const m = /^\[([A-Za-z_][\w]*)\]$/.exec(part);
    if (!m) return <span key={`p-${i}`}>{part}</span>;
    const id = m[1];
    const isReal = citations.includes(id);
    if (!isReal) {
      return (
        <span key={`p-${i}`} className="text-amber-400">
          {part}*
        </span>
      );
    }
    return (
      <button
        key={`p-${i}`}
        onClick={() => onClick?.(id)}
        className="font-mono text-sky-300 underline hover:text-sky-200"
      >
        {part}
      </button>
    );
  });
}