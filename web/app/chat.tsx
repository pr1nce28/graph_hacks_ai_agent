"use client";

/**
 * Chat panel.
 * - Input box with submit (Enter to send).
 * - Streamed assistant answer with clickable citations.
 * - Loading and error states (P4-C-05).
 * - Polished Apple HIG typography, contrast, and subtle borders.
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
  theme?: "dark" | "spiderman";
}

export function Chat({
  messages,
  pending,
  error,
  onSend,
  onCitationClick,
  theme,
}: Props) {
  const [draft, setDraft] = useState("");
  return (
    <div
      className="flex h-full flex-col gap-3 rounded-lg border p-3 transition-colors border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900/60"
      data-testid="chat-panel"
    >
      <div className="flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="text-sm text-slate-500 dark:text-slate-400">
            Ask anything about the company. The agent walks the graph and
            cites the nodes it touched.
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={`msg-${i}`}
            className={
              "rounded-lg border p-2.5 text-sm transition-colors " +
              (m.role === "user"
                ? "border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-slate-100"
                : "border-slate-200 bg-slate-50 text-slate-800 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-100")
            }
          >
            <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">
              {m.role === "user" ? "You" : "OrgMind"}
            </div>
            <div className="mt-1 whitespace-pre-wrap leading-relaxed">
              {renderCitations(m.text, m.citations ?? [], onCitationClick)}
            </div>
            {m.citations && m.citations.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5 pt-1.5 border-t border-slate-100 dark:border-slate-800/60">
                {m.citations.map((c) => (
                  <button
                    key={c}
                    onClick={() => onCitationClick?.(c)}
                    className="rounded border px-1.5 py-0.5 font-mono text-[10px] transition-colors border-red-200 bg-red-50 text-red-700 hover:bg-red-100 dark:border-slate-700/60 dark:bg-slate-800/80 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-white"
                    title={`Focus ${c}`}
                  >
                    [{c}]
                  </button>
                ))}
              </div>
            )}
            {m.dropped && m.dropped.length > 0 && (
              <div className="mt-1 text-[10px] text-red-600/80 dark:text-amber-300/80">
                dropped: {m.dropped.join(", ")}
              </div>
            )}
          </div>
        ))}
        {pending && (
          <div
            className="flex items-center gap-2 rounded-lg border p-2.5 text-sm transition-colors border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-400"
            data-testid="chat-loading"
          >
            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-red-500 dark:bg-blue-400" />
            <span>Thinking… the agent is reasoning over the graph.</span>
          </div>
        )}
        {error && (
          <div
            className="rounded-lg border p-2.5 text-sm border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-950/30 dark:text-red-200"
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
          className="flex-1 rounded-lg border px-3 py-2 text-sm transition-all border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-[#e23636] focus:outline-none focus:ring-1 focus:ring-[#e23636]/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-blue-500 dark:focus:ring-blue-500/30"
          data-testid="chat-input"
        />
        <button
          type="submit"
          disabled={pending || !draft.trim()}
          className="rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors bg-[#e23636] hover:bg-[#c62828] active:bg-[#b71c1c] dark:bg-[#0071e3] dark:hover:bg-[#0077ed] dark:active:bg-[#0062c4] disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 dark:disabled:bg-slate-800 dark:disabled:text-slate-500"
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
  const parts = text.split(/(\[[A-Za-z_][\w]*\])/g);
  return parts.map((part, i) => {
    const m = /^\[([A-Za-z_][\w]*)\]$/.exec(part);
    if (!m) return <span key={`p-${i}`}>{part}</span>;
    const id = m[1];
    const isReal = citations.includes(id);
    if (!isReal) {
      return (
        <span key={`p-${i}`} className="text-amber-300/80">
          {part}*
        </span>
      );
    }
    return (
      <button
        key={`p-${i}`}
        onClick={() => onClick?.(id)}
        className="font-mono text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors"
      >
        {part}
      </button>
    );
  });
}