#!/usr/bin/env bash
# ===================================================================
#  OrgMind - start the API and the web UI
#
#  Runs FastAPI on :8000 and Next.js on :3000. Ctrl+C stops both.
#  Run setup.sh first if you have not.
#
#  Usage:  ./run.sh
# ===================================================================
set -uo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "  The virtual environment is missing. Run ./setup.sh first."
    exit 1
fi

if [ ! -d "web/node_modules" ]; then
    echo "  Web dependencies are missing. Run ./setup.sh first, or:"
    echo "      cd web && npm install"
    exit 1
fi

# Free the ports if a previous run is still holding them.
free_port() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        local pids
        pids=$(lsof -ti :"$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "  freeing port $port (pid $pids)"
            # shellcheck disable=SC2086
            kill $pids 2>/dev/null || true
            sleep 1
        fi
    fi
}
free_port 8000
free_port 3000

echo
echo "=========================================================="
echo "  Starting OrgMind"
echo "=========================================================="
echo
echo "  API  ->  http://localhost:8000"
echo "  Web  ->  http://localhost:3000"
echo
echo "  Ctrl+C stops both."
echo

cleanup() {
    echo
    echo "  shutting down..."
    [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
    [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

# Give the API a moment to bind before the UI starts.
sleep 4

( cd web && npm run dev ) &
WEB_PID=$!

# Wait for the API to answer, then report.
for _ in $(seq 1 20); do
    if .venv/bin/python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)" >/dev/null 2>&1; then
        echo "  [ok] API is up"
        break
    fi
    sleep 1
done

echo
echo "  Open  http://localhost:3000  in your browser."
echo
echo "  First question to try:"
echo "      Why did we choose Postgres over Mongo?"
echo

wait
