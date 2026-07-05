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

    def refine_title(self, topic: TopicRecord, lyrics: str) -> tuple[str, str, dict]:
        prompt = (
            "请为这首中文流行情绪歌生成一个更像正式成品单曲的歌名。\n"
            f"主题：{topic.topic}\n"
            f"情绪：{topic.mood}\n"
            f"场景：{topic.scene}\n"
            f"风格：{topic.style_hint}\n"
            "歌词节选：\n"
            f"{lyrics[:600]}\n\n"
            "要求：\n"
            "1. 输出 3 个候选歌名\n"
            "2. 每个歌名优先控制在 2-8 个汉字，最长不超过 12 个汉字\n"
            "3. 不要直接照搬主题原句，尽量更像正式歌名\n"
            "4. 要有画面感、情绪感、传播感\n"
            "5. 不要加序号、解释、括号备注\n"
            "6. 每行只输出一个歌名"
        )
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You create concise Chinese song titles for commercial music releases.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "stream": False,
            "temperature": 0.7,
        }
        response = self.http_client.post_json(
            url=self.config.base_url.rstrip("/") + "/chat/completions",
            payload=payload,
            bearer_token=self.config.api_key,
            timeout_seconds=self.config.timeout_seconds,
        )
        content = response["choices"][0]["message"]["content"].strip()
        title = _pick_best_title(content, topic.topic)
        return title, prompt, response


def _pick_best_title(content: str, fallback: str) -> str:
    candidates: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip().strip("[]")
        if not line:
            continue
        for prefix in ("1.", "2.", "3.", "1、", "2、", "3、", "-", "•"):
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
        if not line:
            continue
        candidates.append(line[:12].strip())
    for candidate in candidates:
        if 2 <= len(candidate) <= 12 and _looks_like_reasonable_title(candidate):
            return candidate
    compact = fallback.strip()
    return compact[:12] if len(compact) > 12 else compact


def _looks_like_reasonable_title(value: str) -> bool:
    chinese_count = sum("\u4e00" <= char <= "\u9fff" for char in value)
    if chinese_count < 2:
        return False
    disallowed = {"[", "]", "{", "}", "(", ")", ":", "："}
    if any(char in disallowed for char in value):
        return False
    return True
