#!/bin/sh
# Container entry point: start the local Ollama judge (if installed and selected), then the API.
set -e

if command -v ollama > /dev/null 2>&1 && [ "${JUDGE_PROVIDER:-ollama}" = "ollama" ]; then
  ollama serve > /tmp/ollama.log 2>&1 &
  i=0
  until curl -sf http://127.0.0.1:11434/api/version > /dev/null; do
    i=$((i + 1))
    if [ "$i" -ge 90 ]; then
      echo "Ollama did not start in 90 s; the judge will fall back to the hosted model" >&2
      break
    fi
    sleep 1
  done
fi

cd /app/backend
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"
