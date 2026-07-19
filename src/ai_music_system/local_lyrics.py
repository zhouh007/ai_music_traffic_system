from __future__ import annotations

import re

from .models import TopicRecord


def _u(value: str) -> str:
    return value.encode("ascii", "backslashreplace").decode("unicode_escape")


def compose_local_lyrics(topic: TopicRecord) -> str:
    """Compose Chinese lyrics locally without an external language model."""
    observation = _usable_chinese(topic.unique_observation, _u(r"\u6709\u4eba\u603b\u4f1a\u63d0\u524d\u4e00\u70b9\u5230\u8fbe\uff0c\u628a\u676f\u67c4\u8f6c\u5411\u6211\u559c\u6b22\u7684\u90a3\u4e00\u8fb9"))
    scene = _usable_chinese(topic.visual_scene or topic.scene, _u(r"\u96e8\u540e\u7684\u5496\u5561\u5e97\u7a97\u8fb9\u548c\u4e00\u76cf\u5c0f\u5c0f\u7684\u53a8\u623f\u706f"))
    conflict = _usable_chinese(topic.core_conflict, _u(r"\u6211\u62c5\u5fc3\u5e73\u51e1\u7684\u65e5\u5b50\u7559\u4e0d\u4f4f\u5fc3\u52a8"))
    hook = _u(r"\u666e\u901a\u4e5f\u4f1a\u53d8\u751c")
    template = r"""[Verse 1]
{scene}
{observation}
\u628a\u60f3\u8bf4\u7684\u8bdd\u653e\u56de\u53e3\u888b
\u542c\u89c1\u811a\u6b65\u628a\u5b89\u9759\u8d70\u6210\u6b4c

[Pre-Chorus]
{conflict}
{_u(r"\u5374\u6709\u4e00\u76cf\u706f\u66ff\u6211\u4eec\u628a\u65b9\u5411\u7559\u7740")}

[Chorus]
{hook}
{_u(r"\u8ba9\u6bcf\u4e2a\u666e\u901a\u7684\u4eca\u5929\u90fd\u6709\u56de\u58f0")}
{hook}
{_u(r"\u628a\u6ca1\u8bf4\u5b8c\u7684\u8bdd\u4ea4\u7ed9\u660e\u6668")}

[Verse 2]
{_u(r"\u7a97\u8fb9\u7684\u5149\u843d\u5728\u65e7\u7167\u7247\u4e0a")}
{_u(r"\u98ce\u628a\u95e8\u5e18\u5439\u51fa\u8f7b\u8f7b\u7684\u6ce2\u6d6a")}
{_u(r"\u4f60\u8bf4\u4e0d\u7528\u6025\u7740\u8bc1\u660e\u4ec0\u4e48")}
{_u(r"\u966a\u4f34\u672c\u8eab\u5c31\u662f\u7b54\u6848")}
{_u(r"\u665a\u996d\u7684\u70ed\u6c14\u5347\u5230\u5c4b\u9876")}
{_u(r"\u4e24\u53cc\u62d6\u978b\u9760\u5728\u540c\u4e00\u6247\u95e8\u65c1")}

[Bridge]
{_u(r"\u5982\u679c\u660e\u5929\u8fd8\u6709\u4e00\u70b9\u964c\u751f")}
{_u(r"\u5c31\u5e26\u7740\u4eca\u5929\u5b66\u4f1a\u7684\u6e29\u5b58")}
{_u(r"\u6211\u4eec\u5728\u65b0\u7684\u8def\u53e3\u76f8\u8ba4")}

[Final Chorus]
{hook}
{_u(r"\u8ba9\u6bcf\u4e2a\u666e\u901a\u7684\u4eca\u5929\u90fd\u6709\u56de\u58f0")}
{hook}
{_u(r"\u5f53\u6240\u6709\u5c0f\u4e8b\u7ec8\u4e8e\u6709\u4e86\u59d3\u540d")}

[Outro]
\u96e8\u505c\u4ee5\u540e\uff0c\u4ecd\u6709\u4eba\u628a\u706f\u7559\u7740"""
    template = re.sub(r'\{_u\(r"([^"]*)"\)\}', lambda match: _u(match.group(1)), template)
    return _u(template.format(scene=scene, observation=observation, conflict=conflict, hook=hook)).strip()


def select_local_title(topic: TopicRecord) -> str:
    return _u(r"\u5c0f\u5c0f\u5e78\u798f")


def _usable_chinese(value: str, fallback: str) -> str:
    value = " ".join((value or "").split()).strip()
    chinese_count = sum("\u4e00" <= char <= "\u9fff" for char in value)
    mojibake = ("闆", "鏅", "绐", "鍒", "鐨", "閿", "€", "�")
    if chinese_count < 2 or any(mark in value for mark in mojibake):
        return fallback
    return value
