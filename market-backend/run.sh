#!/bin/bash
cd "$(dirname "$0")"
exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080} --reload
