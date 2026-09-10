import os
import requests

base = os.environ.get("CHECK_BASE_URL", "http://127.0.0.1:3000")
password = os.environ.get("ADMIN_PASSWORD", "")
email = os.environ.get("ADMIN_EMAIL", "")
if not password:
    raise SystemExit("ADMIN_PASSWORD is not configured")
for identifier in ("admin", email):
    if not identifier:
        continue
    response = requests.post(
        f"{base}/api/auth/login",
        json={"email_or_username": identifier, "password": password},
        timeout=30,
    )
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    user = payload.get("user") or {}
    print(f"identifier={identifier!r} status={response.status_code} success={response.status_code == 200} username={user.get('username')} role={user.get('role')}")
