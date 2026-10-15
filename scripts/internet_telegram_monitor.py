#!/usr/bin/env python3
"""Independent internet monitor with Telegram notifications.

Secrets are read from environment variables or an EnvironmentFile:
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
Optional:
  CHECK_INTERVAL_SECONDS=60
  STATE_FILE=/var/lib/mabna-market/connectivity-state.json
  CHECK_URL=https://www.google.com/generate_204

Run once for a safe manual test:
  python3 scripts/internet_telegram_monitor.py --once
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_path() -> Path:
    return Path(os.environ.get("STATE_FILE", "./data/standalone-connectivity-state.json")).expanduser()


def read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".connectivity-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def internet_is_up() -> bool:
    url = os.environ.get("CHECK_URL", "https://www.google.com/generate_204")
    try:
        request = Request(url, headers={"User-Agent": "mabna-market-connectivity-monitor/1.0"})
        with urlopen(request, timeout=10) as response:
            return response.status < 500
    except (OSError, URLError):
        return False


def send_telegram(message: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
    payload = urlencode({"chat_id": chat_id, "text": message}).encode()
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "mabna-market-monitor/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        body = json.loads(response.read().decode("utf-8"))
        if response.status >= 300 or not body.get("ok"):
            raise RuntimeError(f"Telegram rejected message: HTTP {response.status}")
    return True


def check_once(path: Path, force_notification: bool = False) -> tuple[bool, str]:
    online = internet_is_up()
    previous = read_state(path)
    previous_online = previous.get("online")
    transition = force_notification or previous_online is not online
    state = {"online": online, "checked_at": now_iso()}
    if transition:
        state["last_transition_at"] = now_iso()
    write_state(path, state)
    if transition:
        if online:
            send_telegram("✅ عاد الاتصال بالإنترنت في جهاز ميني ماركت الفنية.")
        elif previous_online is True:
            send_telegram("⚠️ انقطع الاتصال بالإنترنت في جهاز ميني ماركت الفنية.")
    return online, "transition-notified" if transition else "no-transition"


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor internet and notify Telegram on connectivity transitions")
    parser.add_argument("--once", action="store_true", help="check once and exit")
    parser.add_argument("--notify-now", action="store_true", help="send the current state even without a transition")
    args = parser.parse_args()
    path = state_path()
    interval = max(15, int(os.environ.get("CHECK_INTERVAL_SECONDS", "60")))
    while True:
        try:
            online, result = check_once(path, force_notification=args.notify_now)
            print(f"{now_iso()} online={online} result={result}", flush=True)
        except Exception as exc:
            print(f"{now_iso()} monitor-error={exc}", flush=True)
        if args.once:
            return 0
        time.sleep(interval)
        args.notify_now = False


if __name__ == "__main__":
    raise SystemExit(main())
