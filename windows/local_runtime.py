"""Windows local runtime supervisor for Mini Market Al-Faniya.

This process is intentionally independent from the browser tab. It starts the
local API and UI, watches connectivity, and starts Telegram only when its
admin-saved settings are present and the internet is reachable. Google Drive
backup remains owned by the API scheduler; failures are isolated and logged.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "market-backend"
FRONTEND = ROOT / "artifacts" / "market-frontend"
TELEGRAM = ROOT / "scripts" / "telegram_reports_bot.py"
DATA = BACKEND / "data"
LOGS = ROOT / "windows" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

processes: dict[str, subprocess.Popen] = {}

def log_path(name: str):
    return (LOGS / f"{name}.log").open("a", encoding="utf-8", buffering=1)

def online() -> bool:
    try:
        with urlopen("https://www.google.com/generate_204", timeout=8) as response:
            return response.status < 500
    except Exception:
        return False

def telegram_configured() -> bool:
    path = DATA / "telegram_settings.json"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        cfg = {}
    token = (cfg.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = (cfg.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    return bool(token and chat_id and cfg.get("enabled", True))

def start(name: str, command: list[str], cwd: Path):
    if name in processes and processes[name].poll() is None:
        return
    handle = log_path(name)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(BACKEND))
    processes[name] = subprocess.Popen(command, cwd=str(cwd), env=env, stdout=handle, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

def stop(name: str):
    proc = processes.pop(name, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

def stop_all(*_):
    for name in list(processes):
        stop(name)
    raise SystemExit(0)

def main():
    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)
    python = sys.executable
    start("api", [python, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", os.environ.get("PORT", "8080")], BACKEND)
    start("frontend", ["pnpm.cmd", "dev", "--", "--host", "127.0.0.1", "--port", os.environ.get("UI_PORT", "5173")], FRONTEND)
    last_online = False
    while True:
        is_online = online()
        if is_online and telegram_configured():
            start("telegram", [python, str(TELEGRAM)], ROOT)
        elif not is_online:
            stop("telegram")
        # The API scheduler owns local backup and Drive retry logic. The
        # supervisor only keeps the independent Telegram worker alive.
        last_online = is_online
        for name, proc in list(processes.items()):
            if proc.poll() is not None:
                processes.pop(name, None)
        time.sleep(30)

if __name__ == "__main__":
    main()
