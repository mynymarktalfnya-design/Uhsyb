#!/bin/bash
# Production startup.
# IMPORTANT: keep --workers 1 while using in-memory mongomock; multiple workers
# each have their own isolated in-memory DB, so a token created by Worker-1
# is rejected by Worker-2 (user ID not found) → instant 401 after login.
# When a real shared MongoDB is connected, you may raise workers to 2–4.
cd /home/runner/workspace/market-backend
exec uv run --no-sync uvicorn server:app \
  --host 0.0.0.0 \
  --port "${PORT:-8080}" \
  --workers 1 \
  --log-level info \
  --access-log
