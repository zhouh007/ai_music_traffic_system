from __future__ import annotations

import base64
from pathlib import Path

from ...http import JsonHttpClient
from ...models import ImageProviderConfig


class OpenAICompatibleImageProvider:
    """Generate images through an OpenAI-compatible images endpoint."""

    def __init__(self, config: ImageProviderConfig, http_client: JsonHttpClient) -> None:
        self.config = config
        self.http_client = http_client

    def generate_cover(self, prompt: str, output_path: Path) -> dict:
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "size": self.config.size,
            "n": 1,
        }
        base_url = self.config.base_url.rstrip("/")
        endpoint = base_url if base_url.endswith("/v1") else f"{base_url}/v1"
        response = self.http_client.post_json(
            url=endpoint + "/images/generations",
            payload=payload,
            bearer_token=self.config.api_key,
            timeout_seconds=self.config.timeout_seconds,
        )
        self._write_image_file(response, output_path)
        return response

    def _write_image_file(self, response: dict, output_path: Path) -> None:
        data = response.get("data") or []
        if not data:
            raise ValueError("OpenAI-compatible response did not include image data.")
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
        raise ValueError("OpenAI-compatible response did not include image bytes or URL.")
