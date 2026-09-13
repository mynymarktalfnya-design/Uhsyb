"""Small Google Drive client through the Replit connector proxy.

The connector proxy owns OAuth token refresh. This module only mints the
short-lived Replit identity token and forwards Drive API requests through the
authenticated proxy; no Google credential is stored in the project.
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


class GoogleDriveError(RuntimeError):
    """A user-actionable Google Drive connector error."""


class GoogleDriveClient:
    connector_name = "google-drive"
    default_base_url = "https://connectors.replit.com"

    def __init__(self, timeout: int = 45):
        self.timeout = timeout
        hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME", "").strip()
        if hostname and not hostname.startswith(("http://", "https://")):
            hostname = f"https://{hostname}"
        self.base_url = (hostname or self.default_base_url).rstrip("/")

    def _audience(self) -> str:
        value = os.environ.get("REPLIT_CONNECTORS_AUDIENCE", "").strip()
        if value:
            return value if value.startswith(("http://", "https://")) else f"https://{value}"
        return self.default_base_url

    def _mint_deployment_token(self) -> str | None:
        endpoint = "http://127.0.0.1:1105/getIdentityToken"
        try:
            response = requests.post(
                endpoint,
                json={"audience": self._audience()},
                timeout=5,
            )
            response.raise_for_status()
            token = response.json().get("identityToken", "")
            return token.strip() or None
        except (requests.RequestException, ValueError, AttributeError):
            return None

    def _identity_token(self) -> str:
        is_deployment = any(
            os.environ.get(name)
            for name in (
                "REPLIT_DEPLOYMENT_ID",
                "REPLIT_DEPLOYMENT_ENVIRONMENT",
                "WEB_REPL_RENEWAL",
            )
        ) and not os.environ.get("REPLIT_CONRUN")

        if is_deployment:
            token = self._mint_deployment_token()
            if token:
                return f"depl {token}"

        cli = os.environ.get("REPLIT_CLI", "replit")
        try:
            result = subprocess.run(
                [cli, "identity", "create", "--audience", self._audience()],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            token = result.stdout.strip()
            if token:
                return token
        except (OSError, subprocess.SubprocessError):
            pass

        repl_identity = os.environ.get("REPL_IDENTITY", "").strip()
        if repl_identity:
            return f"repl {repl_identity}"

        token = self._mint_deployment_token()
        if token:
            return f"depl {token}"

        raise GoogleDriveError("تعذر إنشاء هوية Replit للاتصال بـ Google Drive")

    def _headers(self) -> dict[str, str]:
        token = self._identity_token()
        headers = {"Accept": "application/json"}
        if token.startswith(("repl ", "depl ")):
            headers["X-Replit-Token"] = token
        else:
            headers["Replit-Authentication"] = f"Bearer {token}"
        return headers

    def request(self, path: str, method: str = "GET", **kwargs: Any) -> requests.Response:
        normalized = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}/api/v2/proxy{normalized}"
        custom_headers = kwargs.pop("headers", {}) or {}
        headers = self._headers()
        headers["Connector-Name"] = self.connector_name
        headers.update(custom_headers)
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=kwargs.pop("timeout", self.timeout),
            **kwargs,
        )
        if response.status_code == 401:
            headers = self._headers()
            headers["Connector-Name"] = self.connector_name
            headers.update(custom_headers)
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=kwargs.pop("timeout", self.timeout),
                **kwargs,
            )
        return response

    @staticmethod
    def _raise(response: requests.Response, action: str) -> None:
        if response.ok:
            return
        detail = response.text[:400].strip()
        raise GoogleDriveError(
            f"{action} (HTTP {response.status_code})"
            + (f": {detail}" if detail else "")
        )

    @staticmethod
    def _drive_query_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def ensure_backup_folder(self, folder_name: str = "Mini Market Backups") -> dict[str, Any]:
        escaped = self._drive_query_string(folder_name)
        response = self.request(
            "/drive/v3/files",
            params={
                "q": (
                    f"name = '{escaped}' and "
                    "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                ),
                "pageSize": 10,
                "fields": "files(id,name,mimeType,parents,webViewLink)",
            },
        )
        self._raise(response, "تعذر البحث عن مجلد النسخ في Google Drive")
        files = response.json().get("files", [])
        if files:
            return files[0]

        response = self.request(
            "/drive/v3/files",
            method="POST",
            params={"fields": "id,name,mimeType,parents,webViewLink"},
            json={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            },
        )
        self._raise(response, "تعذر إنشاء مجلد النسخ في Google Drive")
        return response.json()

    def upload_file(self, filepath: Path, folder_id: str) -> dict[str, Any]:
        boundary = f"replit-drive-{uuid.uuid4().hex}"
        metadata = json.dumps(
            {
                "name": filepath.name,
                "parents": [folder_id],
                "description": "Mini Market database backup",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        content = filepath.read_bytes()
        body = (
            f"--{boundary}\r\n".encode()
            + b"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            + metadata
            + b"\r\n"
            + f"--{boundary}\r\n".encode()
            + b"Content-Type: application/gzip\r\n"
            + b"Content-Transfer-Encoding: binary\r\n\r\n"
            + content
            + b"\r\n"
            + f"--{boundary}--\r\n".encode()
        )
        response = self.request(
            "/upload/drive/v3/files",
            method="POST",
            params={
                "uploadType": "multipart",
                "fields": "id,name,mimeType,size,modifiedTime,webViewLink,parents",
            },
            headers={
                "Content-Type": f"multipart/related; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
            data=body,
        )
        self._raise(response, f"تعذر رفع النسخة {filepath.name} إلى Google Drive")
        return response.json()

    def list_backup_files(self, folder_id: str | None = None) -> list[dict[str, Any]]:
        """List only database backup archives from the dedicated backup folder."""
        folder = {"id": folder_id} if folder_id else self.ensure_backup_folder()
        response = self.request(
            "/drive/v3/files",
            params={
                "q": f"'{folder['id']}' in parents and trashed = false",
                "pageSize": 100,
                "orderBy": "modifiedTime desc",
                "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink,parents)",
            },
        )
        self._raise(response, "تعذر تحميل نسخ Google Drive")
        files = response.json().get("files", [])
        return [
            file
            for file in files
            if file.get("name", "").startswith("market_db_")
            and file.get("name", "").endswith(".json.gz")
        ]

    def download_file(self, file_id: str) -> bytes:
        """Download a Drive file after the caller has verified its folder."""
        response = self.request(
            f"/drive/v3/files/{quote(file_id, safe='')}",
            params={"alt": "media"},
            timeout=120,
        )
        self._raise(response, "تعذر تنزيل النسخة من Google Drive")
        return response.content


def upload_backup(filepath: Path, state_file: Path) -> dict[str, Any]:
    """Upload one backup and persist the reusable Drive folder id."""
    state: dict[str, Any] = {}
    try:
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}

    client = GoogleDriveClient()
    folder = client.ensure_backup_folder()
    state["folder_id"] = folder["id"]
    state["folder_name"] = folder.get("name", "Mini Market Backups")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return client.upload_file(filepath, folder["id"])