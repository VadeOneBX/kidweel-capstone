#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-api}"

case "$MODE" in
  api)
    exec uvicorn qops.runtime.app:app --host 0.0.0.0 --port "${QOPS_API_PORT:-8000}"
    ;;
  cron)
    exec supercronic /app/docker/crontab
    ;;
  shell)
    exec /bin/bash
    ;;
  *)
    exec "$@"
    ;;
esac
