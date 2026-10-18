#!/usr/bin/env bash
# ===================================================================
#  OrgMind - one-command setup for macOS and Linux
#
#  Checks your tools, creates a Python venv, installs Python and web
#  dependencies, writes .env from the template, and reports whether
#  FalkorDB is reachable. Safe to re-run.
#
#  Usage:  chmod +x setup.sh && ./setup.sh
# ===================================================================
set -uo pipefail
cd "$(dirname "$0")"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; OFF=$'\033[0m'
ok()   { printf "  ${GRN}[ok]${OFF} %s\n" "$1"; }
warn() { printf "  ${YEL}[!]${OFF} %s\n" "$1"; }
bad()  { printf "  ${RED}[X]${OFF} %s\n" "$1"; }

echo
echo "${BOLD}=========================================================="
echo "  OrgMind setup"
echo "==========================================================${OFF}"
echo

FAILED=0
WARNED=0

# ---------------------------------------------------------------- tools
echo "[1/6] Checking required tools..."

if command -v git >/dev/null 2>&1; then ok "$(git --version)"
else bad "git not found. Install from https://git-scm.com/downloads"; FAILED=1; fi

PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)' 2>/dev/null; then
        PY="$c"; break
    fi
done
if [ -n "$PY" ]; then
    ok "$($PY --version 2>&1)"
else
    bad "Python 3.11+ not found. Install from https://www.python.org/downloads/"
    echo "      Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip"
    echo "      macOS:         brew install python@3.12"
    FAILED=1
fi

if command -v node >/dev/null 2>&1; then
    NODE_MAJOR=$(node --version | sed 's/^v\([0-9]*\).*/\1/')
    if [ "$NODE_MAJOR" -ge 18 ]; then ok "node $(node --version)"
    else bad "Node.js 18+ required (found $(node --version))"; FAILED=1; fi
else
    bad "Node.js not found. Install from https://nodejs.org/"; FAILED=1
fi

if command -v npm >/dev/null 2>&1; then ok "npm $(npm --version)"
else bad "npm not found (normally ships with Node.js)"; FAILED=1; fi

if [ "$FAILED" -eq 1 ]; then
    echo
    echo "Setup cannot continue until the [X] items above are installed."
    echo "See docs/SETUP.md for the full prerequisites table."
    echo
    exit 1
fi

# ---------------------------------------------------------------- venv
echo
echo "[2/6] Creating the Python virtual environment..."
if [ -x ".venv/bin/python" ]; then
    ok ".venv already exists"
else
    "$PY" -m venv .venv || { bad "could not create .venv"; exit 1; }
    ok "created .venv"
fi
VENV_PY="$PWD/.venv/bin/python"

# ---------------------------------------------------------------- python deps
echo
echo "[3/6] Installing Python dependencies..."
echo "      (sentence-transformers pulls PyTorch; this can take a few minutes)"
"$VENV_PY" -m pip install --upgrade pip --quiet
if ! "$VENV_PY" -m pip install -e . --quiet; then
    bad "pip install failed - scroll up for the reason"
    exit 1
fi
ok "Python dependencies installed"

# ---------------------------------------------------------------- web deps
echo
echo "[4/6] Installing web dependencies..."
if [ -d "web/node_modules" ]; then
    ok "web/node_modules already exists"
else
    ( cd web && npm install --no-audit --no-fund --loglevel=error ) || { bad "npm install failed"; exit 1; }
    ok "web dependencies installed"
fi

# ---------------------------------------------------------------- .env
echo
echo "[5/6] Configuration..."
if [ -f ".env" ]; then
    ok ".env already exists - leaving it alone"
else
    cp .env.example .env
    ok "created .env from .env.example"
    echo
    echo "  Optional, for a real LLM: put a Gemini key in .env"
    echo "      GEMINI_API_KEY=...      https://aistudio.google.com/apikey"
    echo "  Without one the agent runs demo mode - the graph and tools are"
    echo "  still real, only the planning is scripted."
fi

# ---------------------------------------------------------------- falkordb
echo
echo "[6/6] Checking the graph backend..."
if ! "$VENV_PY" -m scripts.check_graph 2>/dev/null; then
    warn "FalkorDB is not reachable."
    echo "      That is fine: the app falls back to an in-memory graph seeded"
    echo "      from the synthetic data. To use the real database, see"
    echo "      docs/FALKORDB_SETUP.md (Docker or FalkorDB Cloud)."
    WARNED=1
fi

# ---------------------------------------------------------------- done
echo
echo "${BOLD}=========================================================="
echo "  Setup complete"
echo "==========================================================${OFF}"
echo
echo "  Start the project:"
echo "      ./run.sh"
echo
echo "  Then open:  http://localhost:3000"
echo
echo "  Try asking:  Why did we choose Postgres over Mongo?"
echo
if [ "$WARNED" -eq 1 ]; then
    echo "  Note: running without FalkorDB. The in-memory graph is seeded"
    echo "  automatically, so the demo questions still work."
    echo
fi
echo "  Verify everything:"
echo "      .venv/bin/python -m pytest tests/ -q"
echo
