from __future__ import annotations

import binascii
from pathlib import Path

from ...http import JsonHttpClient
from ...models import MusicProviderConfig


class MiniMaxMusicProvider:
    def __init__(self, config: MusicProviderConfig, http_client: JsonHttpClient) -> None:
        self.config = config
        self.http_client = http_client

    def generate_music(
        self,
        lyrics: str,
        title: str,
        style_hint: str,
        output_path: Path,
        generation_mode: str = "text_to_music",
        reference_audio_url: str = "",
    ) -> dict:
        payload = self._build_payload(
            lyrics=lyrics,
            style_hint=style_hint,
            generation_mode=generation_mode,
            reference_audio_url=reference_audio_url,
        )
        response = self.http_client.post_json(
            url=self.config.base_url.rstrip("/") + "/music_generation",
            payload=payload,
            bearer_token=self.config.api_key,
            timeout_seconds=self.config.timeout_seconds,
        )
        self._write_audio_file(response, output_path)
        response["requested_title"] = title
        return response

    def _build_payload(
        self,
        lyrics: str,
        style_hint: str,
        generation_mode: str,
        reference_audio_url: str,
    ) -> dict:
        mode = (generation_mode or "text_to_music").strip().lower()
        payload = {
            "prompt": style_hint,
            "lyrics": lyrics,
            "output_format": self.config.output_format,
            "audio_setting": {
                "sample_rate": self.config.sample_rate,
                "bitrate": self.config.bitrate,
                "format": self.config.audio_format,
            },
        }
        if mode == "reference_audio":
            if not reference_audio_url.strip():
                raise ValueError("reference_audio mode requires reference_audio_url.")
            payload["model"] = self.config.cover_model
            payload["audio_url"] = reference_audio_url.strip()
        else:
            payload["model"] = self.config.model
        return payload

    def _write_audio_file(self, response: dict, output_path: Path) -> None:
        audio_value = response.get("data", {}).get("audio")
        if not audio_value:
            raise ValueError("MiniMax response did not include audio data.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.config.output_format == "url":
            self.http_client.download_file(
                url=audio_value,
                output_path=output_path,
                timeout_seconds=self.config.timeout_seconds,
            )
            return
        audio_bytes = binascii.unhexlify(audio_value)
        output_path.write_bytes(audio_bytes)
