#!/usr/bin/env bash
# One command to set up and verify the project from a fresh clone (macOS or Linux).
# Usage, from the project root:  bash scripts/setup_and_check.sh
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf "\n==> %s\n" "$1"; }

step "Checking tools"
command -v python3 >/dev/null || { echo "Install Python 3 first."; exit 1; }
command -v node >/dev/null || { echo "Install Node 24 (see .nvmrc) first."; exit 1; }
echo "python $(python3 --version | cut -d' ' -f2), node $(node -v)"

step "Python environment"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q -r requirements.txt

step "API key"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Put your PORTKEY_API_KEY in .env before running the agents."
fi
grep -q "your-portkey-key-here" .env && echo "WARNING: .env still has the placeholder key. Agent runs will fail until you add your key."

step "Dashboard dependencies"
(cd frontend && npm install --silent && npm run build --silent >/dev/null)
echo "dashboard builds"

step "Reset the working database to the original values"
cp data/campus_customs.db data/campus_customs_new.db
echo "data/campus_customs_new.db restored from data/campus_customs.db"

step "Tests (no model calls)"
./.venv/bin/python -m pytest -q tests

step "MCP server check (launches the server exactly as .mcp.json describes)"
./.venv/bin/python tests/mcp_smoke.py | grep -E "MATCH|MISMATCH"

step "Setup and checks passed. Next: see README.md, 'Running the app'."
