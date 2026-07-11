from __future__ import annotations

import hashlib
import re

from .models import SongRecord, TopicRecord


COVER_FAMILIES = [
    ("human_story", "A candid human moment with an unusual pose and asymmetrical editorial framing; environment carries equal narrative weight."),
    ("still_life", "No person. Build a poetic still life from two or three concrete lyric objects with directional light and generous negative space."),
    ("city_environment", "No portrait. Show a quiet everyday public place such as a corridor, bus stop, rooftop, convenience-store exterior, or rain-washed crossing."),
    ("natural_metaphor", "Full-frame uninhabited outdoor landscape. Wind moves through tall grass beside reflective water; layered clouds open above distant hills in changing evening light. The complete image inventory is grass, water, clouds, hills, sky, wind, and natural light."),
    ("abstract_editorial", "No literal character scene. Use restrained paper collage, geometric fields, imperfect ink shapes, and one symbolic object."),
]

PALETTES = [
    "mist blue, warm white, leaf green, and a small amber accent",
    "soft coral, charcoal, pale cyan, and off-white",
    "sage green, muted yellow, ink gray, and clear sky blue",
    "dusty rose, deep forest green, cream, and restrained red",
    "cobalt blue, pale lemon, paper white, and graphite gray",
]


def build_cover_direction(song: SongRecord, topic: TopicRecord, lyrics: str) -> dict:
    index = int(hashlib.sha256(song.song_id.encode("utf-8")).hexdigest()[:8], 16) % len(COVER_FAMILIES)
    family, composition = COVER_FAMILIES[index]
    return {
        "cover_family": family,
        "composition_direction": composition,
        "palette_direction": PALETTES[index],
        "lyric_imagery": extract_lyric_imagery(lyrics),
    }


def extract_lyric_imagery(lyrics: str) -> str:
    objects = ["钥匙", "玄关", "杯", "水", "窗帘", "晚风", "纸", "灯", "雨", "车站", "树影", "云", "月光", "鞋", "桌"]
    found = [value for value in objects if value in lyrics]
    return ", ".join(found[:4]) if found else "one concrete everyday object and one natural element from the song scene"


def format_cover_prompt(template: str, song: SongRecord, topic: TopicRecord, lyrics: str) -> tuple[str, dict]:
    direction = build_cover_direction(song, topic, lyrics)
    prompt = template.format(topic=topic.topic, mood=topic.mood, scene=topic.scene, style_hint=topic.style_hint, **direction)
    return prompt, direction
