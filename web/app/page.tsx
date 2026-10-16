"use client";

import { useEffect, useState } from "react";

type Info = {
  name: string;
  phase: number;
  tracks: string[];
};

const API_BASE = "http://localhost:8000";

export default function HomePage() {
  const [info, setInfo] = useState<Info | null>(null);
  const [status, setStatus] = useState<"idle" | "connected" | "error">(
    "idle",
  );

  useEffect(() => {
    let cancelled = false;

    fetch(`${API_BASE}/info`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return res.json() as Promise<Info>;
      })
      .then((data) => {
        if (cancelled) return;
        setInfo(data);
        setStatus("connected");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const tracks = info?.tracks ?? [
    "agents-on-connected-data",
    "memory-coordination",
    "company-brain",
  ];

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-4xl font-semibold tracking-tight text-slate-50">
          OrgMind
        </h1>
        <p className="text-base text-slate-400">
          Company Brain {"\u00b7"} FalkorDB
        </p>
      </header>

      <section className="flex items-center gap-3">
        <span
          className={
            "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium " +
            (status === "connected"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
              : status === "error"
                ? "border-rose-500/40 bg-rose-500/10 text-rose-300"
                : "border-slate-700 bg-slate-800/60 text-slate-300")
          }
          data-testid="status-pill"
        >
          <span
            className={
              "h-2 w-2 rounded-full " +
              (status === "connected"
                ? "bg-emerald-400"
                : status === "error"
                  ? "bg-rose-400"
                  : "bg-slate-500")
            }
            aria-hidden="true"
          />
          {status === "connected"
            ? "API connected"
            : status === "error"
              ? "API unreachable"
              : "Connecting..."}
        </span>
        <span className="text-xs text-slate-500">
          {info ? `phase ${info.phase}` : "phase 0"}
        </span>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-black/30 backdrop-blur">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Tracks
        </h2>
        <ul className="mt-4 grid gap-3 sm:grid-cols-3">
          {tracks.map((track) => (
            <li
              key={track}
              className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-200"
            >
              {track}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}