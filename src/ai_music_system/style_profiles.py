from __future__ import annotations


STYLE_PROFILES = {
    "nature_healing": {
        "label_zh": "自然治愈",
        "creative_mode": "healing_gentle",
        "style_hint": (
            "slow atmospheric healing Chinese pop, nature imagery, non-narrative, "
            "airy and spacious, delicate long and short phrases"
        ),
    },
    "healing_gentle": {
        "label_zh": "温柔治愈",
        "creative_mode": "healing_gentle",
        "style_hint": "slow healing Chinese pop, warm acoustic arrangement, spacious vocal phrasing",
    },
    "mood_atmosphere": {
        "label_zh": "氛围情绪",
        "creative_mode": "mood",
        "style_hint": "atmospheric Chinese pop, sensory and immersive, minimal narrative",
    },
    "slice_of_life": {
        "label_zh": "生活切片",
        "creative_mode": "slice_of_life",
        "style_hint": "intimate Chinese pop, concrete everyday imagery, snapshot-based writing",
    },
}


STYLE_TAG_ALIASES = {
    "自然治愈": "nature_healing",
    "自然意象治愈": "nature_healing",
    "自然风景治愈": "nature_healing",
    "温柔治愈": "healing_gentle",
    "治愈系": "healing_gentle",
    "氛围情绪": "mood_atmosphere",
    "氛围流行": "mood_atmosphere",
    "生活切片": "slice_of_life",
    "日常切片": "slice_of_life",
}


def normalize_style_tag(style_tag: str) -> str:
    value = (style_tag or "").strip().lower()
    return STYLE_TAG_ALIASES.get(value, value)


def expand_style_tag(style_tag: str) -> dict[str, str]:
    return dict(STYLE_PROFILES.get(normalize_style_tag(style_tag), {}))
