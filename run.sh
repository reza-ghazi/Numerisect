#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

python_command="python3"
if [[ -x "$project_dir/.venv/bin/python" ]]; then
  python_command="$project_dir/.venv/bin/python"
fi

export PYTHONPATH="$project_dir${PYTHONPATH:+:$PYTHONPATH}"

ui_url="http://127.0.0.1:8765/?ui=20260905-workstation#primes/prime-check"
echo "Numerisect source: $project_dir"
echo "Numerisect interface: $project_dir/static"
echo "Opening: $ui_url"

if [[ "${NUMERISECT_NO_BROWSER:-0}" != "1" ]] && command -v xdg-open >/dev/null 2>&1; then
  (
    sleep 1
    xdg-open "$ui_url" >/dev/null 2>&1 || true
  ) &
fi

exec "$python_command" -m uvicorn numerisect.main:app \
  --app-dir "$project_dir" \
  --host 127.0.0.1 \
  --port 8765
