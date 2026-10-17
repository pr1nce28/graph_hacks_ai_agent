"""Render the architecture diagram to PNG.

> Implements P6-C-02. Uses matplotlib to draw boxes and arrows for the
> system architecture described in ARCHITECTURE.md §2.1. No browser
> required.

Run:

    python -m scripts.render_architecture

Writes ``docs/architecture.png``.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")  # noqa: E402
    import matplotlib.pyplot as plt  # noqa: E402
    from matplotlib.patches import FancyBboxPatch  # noqa: E402
except ImportError:  # pragma: no cover - optional
    HAS_MPL = False
else:
    HAS_MPL = True


LAYERS = [
    ("Next.js UI\n(Chat │ Graph │ Path │ Memory │ Timeline)", "#0f172a", "#cbd5e1"),
    ("FastAPI\n(api/)", "#1e293b", "#cbd5e1"),
    ("Orchestrator + Analyst + Action + Ingestion", "#0f172a", "#cbd5e1"),
    ("Tool Registry (in-process or MCP)", "#1e293b", "#cbd5e1"),
    ("Memory: semantic · episodic · procedural · coordination", "#0f172a", "#cbd5e1"),
    ("Graph: client · queries · embeddings", "#1e293b", "#cbd5e1"),
    ("FalkorDB (org_acme, org_globex)", "#0f172a", "#cbd5e1"),
]


def main() -> int:
    if not HAS_MPL:  # pragma: no cover
        print(
            "matplotlib not installed; skipping PNG render. "
            "The ASCII diagram in docs/architecture.png.meta is the source of truth.",
            file=sys.stderr,
        )
        return 0

    fig, ax = plt.subplots(figsize=(8, 7))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(LAYERS) + 1)
    ax.axis("off")

    width = 8.0
    x = (10 - width) / 2
    for i, (text, fc, ec) in enumerate(LAYERS):
        y = len(LAYERS) - i - 0.9
        rect = FancyBboxPatch(
            (x, y - 0.4),
            width,
            0.8,
            boxstyle="round,pad=0.02,rounding_size=0.1",
            facecolor=fc,
            edgecolor=ec,
            linewidth=1.0,
        )
        ax.add_patch(rect)
        ax.text(
            x + width / 2,
            y,
            text,
            ha="center",
            va="center",
            color="white",
            fontsize=10,
        )
        # Arrow downward to the next box.
        if i < len(LAYERS) - 1:
            ax.annotate(
                "",
                xy=(x + width / 2, y - 0.55),
                xytext=(x + width / 2, y - 0.95),
                arrowprops=dict(arrowstyle="-|>", color="#94a3b8", lw=1.2),
            )

    out_path = Path(__file__).resolve().parent.parent / "docs" / "architecture.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())