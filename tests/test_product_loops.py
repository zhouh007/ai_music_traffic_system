from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_music_system.experiments import ExperimentStore
from ai_music_system.performance import PerformanceStore
from ai_music_system.models import SongRecord, TopicRecord
from ai_music_system.quality import evaluate_quality


class PerformanceStoreTests(unittest.TestCase):
    def test_summary_uses_latest_snapshot_per_song(self):
        with tempfile.TemporaryDirectory() as temp:
            store = PerformanceStore(Path(temp))
            store.record(song_id="song_1", platform="fanqie_music", views=10, favorites=1)
            store.record(song_id="song_1", platform="fanqie_music", views=20, favorites=3)
            summary = store.summarize(platform="fanqie_music")
            self.assertEqual(summary["record_count"], 2)
            self.assertEqual(summary["totals"]["views"], 20)
            self.assertEqual(summary["totals"]["favorites"], 3)


class ExperimentStoreTests(unittest.TestCase):
    def test_create_and_attach_songs_without_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ExperimentStore(Path(temp))
            record = store.create(name="hook", hypothesis="earlier is better", variable="hook timing", control_prompt_version="v1", variant_prompt_version="v2", primary_metric="favorites")
            updated = store.update(record.experiment_id, "running", ["song_1", "song_1"])
            self.assertEqual(updated.status, "running")
            self.assertEqual(updated.song_ids, ["song_1"])


class QualityGateTests(unittest.TestCase):
    def test_missing_assets_fail_hard_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            song = SongRecord(song_id="song_1", topic_id="topic_1", batch_id="batch_1", title="title", mode="text_to_music", status="generated", song_dir=root, lyrics_raw_path=root / "raw.txt", lyrics_clean_path=root / "clean.txt", audio_path=root / "audio.mp3", cover_raw_path=root / "raw.png", cover_publish_path=root / "cover.png", cover_hd_path=root / "hd.png", meta_path=root / "meta.json", caption_path=root / "caption.txt", review_path=root / "review.json")
            topic = TopicRecord(topic_id="topic_1", batch_id="batch_1", topic="topic", audience="all", mood="warm", scene="home", style_hint="pop", publish_platform="douyin", distribution_target="short_video")
            result = evaluate_quality(song, topic)
            self.assertFalse(result["hard_gate_passed"])
            self.assertIn("audio_present", result["failed_gates"])


if __name__ == "__main__":
    unittest.main()
