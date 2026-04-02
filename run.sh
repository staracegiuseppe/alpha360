#!/usr/bin/env bash
set -e

echo "============================================"
echo "  Alpha360 — Unified Security Analysis"
echo "  & Financial Planner"
echo "============================================"

CONFIG_PATH=/data/options.json

if [ ! -f "$CONFIG_PATH" ]; then
    echo "[Alpha360] WARN: options.json not found, using defaults"
    echo '{}' > "$CONFIG_PATH"
fi

echo "[Alpha360] Options loaded from $CONFIG_PATH"
echo "[Alpha360] Starting server on port 8099..."

cd /app
exec python3 server.py
