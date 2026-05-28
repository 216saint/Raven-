#!/usr/bin/env bash
# raven.sh — POSIX launcher for Raven. Parity with raven.ps1 on Windows.
#
# Usage:
#   ./raven.sh                  # default port 8501
#   ./raven.sh --skip-install   # don't pip install (assume venv ready)
#   ./raven.sh --port 8600

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

PORT="8501"
SKIP_INSTALL=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        --skip-install) SKIP_INSTALL=1; shift ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

step() { printf "==> %s\n" "$*"; }
warn() { printf "!! %s\n" "$*" >&2; }
err()  { printf "XX %s\n" "$*" >&2; }

# ---------------------------------------------------------------------------
# Step 1: Python 3.10+
# ---------------------------------------------------------------------------
step "Checking Python..."
PYTHON=""
for cand in python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
            PYTHON="$cand"
            echo "    found: $($cand --version)"
            break
        fi
    fi
done
if [[ -z "$PYTHON" ]]; then
    err "Python 3.10+ not found. Install via your package manager and re-run."
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 2: venv
# ---------------------------------------------------------------------------
VENV="$REPO_ROOT/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
    step "Creating virtualenv .venv/ ..."
    "$PYTHON" -m venv "$VENV"
fi

# ---------------------------------------------------------------------------
# Step 3: deps
# ---------------------------------------------------------------------------
if [[ $SKIP_INSTALL -eq 0 ]]; then
    step "Installing Python dependencies..."
    "$VENV/bin/python" -m pip install --upgrade pip --quiet
    "$VENV/bin/python" -m pip install -r requirements.txt --quiet
fi

# ---------------------------------------------------------------------------
# Step 4: Tor
# ---------------------------------------------------------------------------
mkdir -p "$REPO_ROOT/.raven"
TOR_PIDFILE="$REPO_ROOT/.raven/tor.pid"

tor_running() {
    (echo >/dev/tcp/127.0.0.1/9050) >/dev/null 2>&1
}

if tor_running; then
    step "Tor already listening on 127.0.0.1:9050 — reusing it."
elif command -v tor >/dev/null 2>&1; then
    step "Starting system tor..."
    tor --quiet --RunAsDaemon 0 &
    echo $! > "$TOR_PIDFILE"
    for _ in {1..20}; do
        sleep 0.5
        tor_running && break
    done
    tor_running || warn "Tor did not open 9050 within 10s."
else
    warn "Tor binary not found. Install with:"
    warn "  sudo apt install tor       (Debian/Ubuntu)"
    warn "  brew install tor           (macOS)"
    warn "Scraping .onion will fail without it."
fi

cleanup() {
    if [[ -f "$TOR_PIDFILE" ]]; then
        pid="$(cat "$TOR_PIDFILE" 2>/dev/null || true)"
        if [[ -n "${pid:-}" ]]; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$TOR_PIDFILE"
    fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Step 5: Streamlit
# ---------------------------------------------------------------------------
step "Launching Raven on http://localhost:$PORT ..."
exec "$VENV/bin/python" -m streamlit run ui.py \
    --server.port "$PORT" --server.headless true
