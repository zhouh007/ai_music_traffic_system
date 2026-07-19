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
            user_need=topic.user_need,
            core_conflict=topic.core_conflict,
            unique_observation=topic.unique_observation,
            emotional_payoff=topic.emotional_payoff,
            visual_scene=topic.visual_scene,
            series_name=topic.series_name,
        )
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You write original, singable Chinese lyrics."},
                {"role": "user", "content": prompt},
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
            "请为这首中文歌曲提供 3 个正式、具体、容易记住的候选歌名。\n"
            f"主题：{topic.topic}\n场景：{topic.scene}\n独特观察：{topic.unique_observation}\n"
            f"情绪回报：{topic.emotional_payoff}\n歌词片段：\n{lyrics[:800]}\n\n"
            "只输出 3 行歌名，不要编号、解释、引号或标签。避免空泛励志词和短视频口号。"
        )
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You create concise Chinese song titles for commercial music releases."},
                {"role": "user", "content": prompt},
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
        return _pick_best_title(content, topic.topic), prompt, response


def _pick_best_title(content: str, fallback: str) -> str:
    candidates: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip().strip("[]\"'。")
        for prefix in ("1.", "2.", "3.", "1、", "2、", "3、", "-", "•"):
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
        if 2 <= len(line) <= 12 and _looks_like_reasonable_title(line):
            candidates.append(line)
    return candidates[0] if candidates else fallback.strip()[:12]


def _looks_like_reasonable_title(value: str) -> bool:
    chinese_count = sum("\u4e00" <= char <= "\u9fff" for char in value)
    disallowed = {"[", "]", "{", "}", "(", ")", ":", "："}
    return chinese_count >= 2 and not any(char in disallowed for char in value)
