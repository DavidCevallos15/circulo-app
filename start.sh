#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
if [[ ! -f dist/index.html ]]; then npm ci; npm run build; fi
exec .venv/bin/python -m runner.server
