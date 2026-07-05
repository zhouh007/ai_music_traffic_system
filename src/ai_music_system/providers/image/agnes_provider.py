from __future__ import annotations

import base64
from pathlib import Path

from ...http import JsonHttpClient
from ...models import ImageProviderConfig


class AgnesImageProvider:
    def __init__(self, config: ImageProviderConfig, http_client: JsonHttpClient) -> None:
        self.config = config
        self.http_client = http_client

    def generate_cover(
        self,
        prompt: str,
        output_path: Path,
    ) -> dict:
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "size": self.config.size,
            "return_base64": self.config.return_base64,
        }
        if not self.config.return_base64:
            payload["extra_body"] = {"response_format": "url"}
        response = self.http_client.post_json(
            url=self.config.base_url.rstrip("/") + "/images/generations",
            payload=payload,
            bearer_token=self.config.api_key,
            timeout_seconds=self.config.timeout_seconds,
        )
        self._write_image_file(response, output_path)
        return response

    def _write_image_file(self, response: dict, output_path: Path) -> None:
        data = response.get("data") or []
        if not data:
            raise ValueError("Agnes response did not include image data.")
        first = data[0]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if first.get("b64_json"):
            output_path.write_bytes(base64.b64decode(first["b64_json"]))
            return
        if first.get("url"):
            self.http_client.download_file(
                url=first["url"],
                output_path=output_path,
                timeout_seconds=self.config.timeout_seconds,
            )
            return
        raise ValueError("Agnes response did not include image bytes or URL.")
