from __future__ import annotations

from ...http import JsonHttpClient
from ...models import LyricsProviderConfig, TopicRecord


class DeepSeekLyricsProvider:
    def __init__(self, config: LyricsProviderConfig, http_client: JsonHttpClient) -> None:
        self.config = config
        self.http_client = http_client

    def generate_lyrics(self, topic: TopicRecord, prompt_template: str) -> tuple[str, str, dict]:
        prompt = prompt_template.format(
            topic=topic.topic,
            audience=topic.audience,
            mood=topic.mood,
            scene=topic.scene,
            style_hint=topic.style_hint,
            distribution_target=topic.distribution_target,
        )
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You write concise, singable Chinese lyrics for short-form music content.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "stream": False,
            "temperature": self.config.temperature,
        }
        response = self.http_client.post_json(
            url=self.config.base_url.rstrip("/") + "/chat/completions",
            payload=payload,
            bearer_token=self.config.api_key,
            timeout_seconds=self.config.timeout_seconds,
        )
        lyrics = response["choices"][0]["message"]["content"].strip()
        return lyrics, prompt, response
