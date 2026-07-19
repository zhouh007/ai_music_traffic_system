from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import TopicRecord
from .platform_profiles import infer_distribution_target


TOPIC_FIELDNAMES = [
    "topic_id",
    "batch_id",
    "topic",
    "audience",
    "mood",
    "scene",
    "style_hint",
    "style_tag",
    "publish_platform",
    "status",
    "generation_mode",
    "reference_audio_url",
    "distribution_target",
    "user_need",
    "core_conflict",
    "unique_observation",
    "emotional_payoff",
    "visual_scene",
    "series_name",
]


def load_topics_from_csv(csv_path: Path) -> list[TopicRecord]:
    topics: list[TopicRecord] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            topics.append(TopicRecord(**row))
    return topics


def write_topics_to_csv(csv_path: Path, topics: list[TopicRecord]) -> Path:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TOPIC_FIELDNAMES)
        writer.writeheader()
        for topic in topics:
            writer.writerow(topic.model_dump())
    return csv_path


def build_topic_record(
    *,
    batch_id: str,
    index: int,
    topic: str,
    audience: str,
    mood: str,
    scene: str,
    style_hint: str,
    style_tag: str = "",
    publish_platform: str,
    generation_mode: str = "text_to_music",
    reference_audio_url: str = "",
    distribution_target: str = "hybrid",
    user_need: str = "",
    core_conflict: str = "",
    unique_observation: str = "",
    emotional_payoff: str = "",
    visual_scene: str = "",
    series_name: str = "",
) -> TopicRecord:
    normalized_distribution_target = infer_distribution_target(distribution_target, publish_platform)
    return TopicRecord(
        topic_id=f"tp_{datetime.now():%Y%m%d}_{index:03d}",
        batch_id=batch_id,
        topic=topic.strip(),
        audience=audience.strip(),
        mood=mood.strip(),
        scene=scene.strip(),
        style_hint=style_hint.strip(),
        style_tag=style_tag.strip(),
        publish_platform=publish_platform.strip(),
        status="pending",
        generation_mode=generation_mode.strip() or "text_to_music",
        reference_audio_url=reference_audio_url.strip(),
        distribution_target=normalized_distribution_target,
        user_need=user_need.strip(),
        core_conflict=core_conflict.strip(),
        unique_observation=unique_observation.strip(),
        emotional_payoff=emotional_payoff.strip(),
        visual_scene=visual_scene.strip(),
        series_name=series_name.strip(),
    )
