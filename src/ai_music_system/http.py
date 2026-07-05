from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path


class JsonHttpClient:
    def __init__(self) -> None:
        self._ssl_context = ssl.create_default_context()

    def post_json(
        self,
        url: str,
        payload: dict,
        bearer_token: str,
        timeout_seconds: int,
    ) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=data,
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds, context=self._ssl_context) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} for {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Request failed for {url}: {exc.reason}") from exc

    def download_file(
        self,
        url: str,
        output_path: Path,
        timeout_seconds: int,
    ) -> None:
        request = urllib.request.Request(url=url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds, context=self._ssl_context) as response:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Download failed with HTTP {exc.code} for {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Download failed for {url}: {exc.reason}") from exc
