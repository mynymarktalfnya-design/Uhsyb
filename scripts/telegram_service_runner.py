#!/usr/bin/env python3
"""Portable supervisor for the Telegram reports bot on Windows.

Loads secrets from a machine-local env file, starts the existing bot process,
restarts crashes with bounded exponential backoff, and writes a redacted health
status file. It does not contain Telegram or database secrets.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SERVICE_NAME = "MMFTelegramBotService"


def load_env(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Environment file not found: {path}")
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in {"PYTHONPATH", "PYTHONHOME"}:
            os.environ[key] = value


def safe_env_summary() -> dict[str, str]:
    return {
        "database_configured": str(bool(os.environ.get("MONGO_URL") or os.environ.get("NEON_DATABASE_URL"))),
        "telegram_configured": str(bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))),
        "allowed_chat_ids_configured": str(bool(os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS"))),
        "service": SERVICE_NAME,
    }


def write_status(path: Path, state: str, **extra) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "service": SERVICE_NAME,
        "state": state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **safe_env_summary(),
        **extra,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--status-file", type=Path, default=None)
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    status_file = (args.status_file or Path(os.environ.get("PROGRAMDATA", project_root / "data")) / "MMF" / "telegram-bot-status.json").resolve()
    log_dir = status_file.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_dir / "telegram-service-supervisor.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        load_env(args.env_file.resolve())
        write_status(status_file, "STARTING", pid=os.getpid())
    except Exception as exc:
        write_status(status_file, "ERROR", error=str(exc)[:300])
        logging.exception("startup configuration failed")
        return 2

    bot = project_root / "scripts" / "telegram_reports_bot.py"
    if not bot.exists():
        write_status(status_file, "ERROR", error="telegram_reports_bot.py not found")
        logging.error("bot script not found: %s", bot)
        return 2

    backoff = 5
    while True:
        child = None
        try:
            logging.info("starting Telegram bot process")
            child = subprocess.Popen([sys.executable, str(bot)], cwd=str(project_root), env=os.environ.copy())
            write_status(status_file, "RUNNING", pid=child.pid, bot=str(bot))
            logging.info("Telegram bot started pid=%s; configuration=%s", child.pid, safe_env_summary())
            code = child.wait()
            write_status(status_file, "ERROR", exit_code=code, last_pid=child.pid)
            logging.error("Telegram bot exited with code=%s; restarting", code)
        except KeyboardInterrupt:
            if child and child.poll() is None:
                child.terminate()
            write_status(status_file, "STOPPED")
            return 0
        except Exception as exc:
            write_status(status_file, "ERROR", error=str(exc)[:300])
            logging.exception("supervisor error")
        time.sleep(backoff)
        backoff = min(backoff * 2, 300)
        logging.info("restarting Telegram bot after backoff_seconds=%s", backoff)


if __name__ == "__main__":
    raise SystemExit(main())
