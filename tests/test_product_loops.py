from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_music_system.experiments import ExperimentStore
from ai_music_system.performance import PerformanceStore
from ai_music_system.models import SongRecord, TopicRecord
from ai_music_system.quality import evaluate_quality
from ai_music_system.lyrics_prompting import load_lyrics_prompt
from ai_music_system.pipeline.package_builder import build_caption
from ai_music_system.platform_profiles import audio_constraints
from ai_music_system.audio_review import detect_first_vocal_entry
from ai_music_system.local_lyrics import compose_local_lyrics, select_local_title


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

    def test_mojibake_fails_text_integrity_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clean = root / "clean.txt"
            clean.write_text("锟斤拷", encoding="utf-8")
            song = SongRecord(song_id="song_1", topic_id="topic_1", batch_id="batch_1", title="title", mode="text_to_music", status="generated", song_dir=root, lyrics_raw_path=root / "raw.txt", lyrics_clean_path=clean, audio_path=root / "audio.mp3", cover_raw_path=root / "raw.png", cover_publish_path=root / "cover.png", cover_hd_path=root / "hd.png", meta_path=root / "meta.json", caption_path=root / "caption.txt", review_path=root / "review.json")
            topic = TopicRecord(topic_id="topic_1", batch_id="batch_1", topic="topic", audience="all", mood="warm", scene="home", style_hint="pop", publish_platform="douyin", distribution_target="short_video")
            result = evaluate_quality(song, topic)
            self.assertFalse(result["gates"]["text_integrity_valid"])


class CreativeBriefTests(unittest.TestCase):
    def test_style_tag_expands_to_reusable_nature_healing_profile(self):
        topic = TopicRecord(
            topic_id="tp_style",
            batch_id="batch",
            topic="云",
            audience="听众",
            mood="安静",
            scene="雨后山谷",
            publish_platform="fanqie_music",
            distribution_target="music_platform",
            style_tag="nature_healing",
        )
        self.assertEqual(topic.creative_mode, "healing_gentle")
        self.assertIn("nature imagery", topic.style_hint)

        chinese_topic = topic.model_copy(update={"style_tag": "自然治愈"})
        chinese_topic = TopicRecord.model_validate(chinese_topic.model_dump())
        self.assertEqual(chinese_topic.style_tag, "nature_healing")
        self.assertEqual(chinese_topic.creative_mode, "healing_gentle")


    def test_prompt_contains_clean_brief_and_profile(self):
        topic = TopicRecord(topic_id="tp_1", batch_id="batch", topic="雨夜回家", audience="下班独居者", mood="释然", scene="公交站", style_hint="流行", publish_platform="douyin", distribution_target="short_video", user_need="给疲惫的人一个缓冲", core_conflict="想联系旧友却停在输入框", unique_observation="删除聊天框后仍会点开头像", emotional_payoff="从犹豫走向轻松", visual_scene="末班车玻璃上的倒影", series_name="夜路短歌")
        prompt, target = load_lyrics_prompt(Path.cwd(), topic)
        self.assertEqual(target, "short_video")
        self.assertIn("删除聊天框后仍会点开头像", prompt)
        self.assertIn("SHORT_VIDEO_PROFILE", prompt)
        self.assertIn("[Chorus]", prompt)

    def test_music_platform_prompt_contains_timing_and_full_song_rules(self):
        topic = TopicRecord(topic_id="tp_2", batch_id="batch", topic="small happiness", audience="listeners", mood="sweet", scene="cafe", style_hint="pop", publish_platform="qishui_music", distribution_target="music_platform", creative_mode="healing_gentle", user_need="a complete song", core_conflict="fear that ordinary love is not special", unique_observation="the early person orders the usual drink", emotional_payoff="warm certainty", visual_scene="two cups by a rainy window")
        prompt, target = load_lyrics_prompt(Path.cwd(), topic)
        self.assertEqual(target, "music_platform")
        self.assertIn("Vocal must start within the first 5-10 seconds", prompt)
        self.assertIn("repetition patterns that fit the creative mode", prompt)
        self.assertIn("one core line of 5-10 Chinese characters", prompt)
        self.assertIn("invite the listener into the feeling without requiring a plot", prompt)
        self.assertIn("nature and sensory imagery", prompt)
        self.assertIn("no plot or character narration", prompt)
        self.assertIn("breathing room for instrumental motifs", prompt)

    def test_mood_mode_does_not_require_narrative_bridge(self):
        topic = TopicRecord(topic_id="tp_mood", batch_id="batch", topic="soft light", audience="listeners", mood="calm", scene="room", style_hint="slow pop", publish_platform="qishui_music", distribution_target="music_platform", creative_mode="mood")
        lyrics = "[Verse 1]\n" + "光落在窗边 " * 60 + "\n[Chorus]\n" + "慢一点也很好\n" * 12 + "\n[Outro]\n灯还亮着"
        from ai_music_system.quality import _has_song_structure
        self.assertTrue(_has_song_structure(lyrics, True, topic.creative_mode))

    def test_caption_uses_readable_runtime_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            song = SongRecord(song_id="song_1", topic_id="topic_1", batch_id="batch_1", title="夜路", mode="text_to_music", status="generated", song_dir=root, lyrics_raw_path=root / "raw.txt", lyrics_clean_path=root / "clean.txt", audio_path=root / "audio.mp3", cover_raw_path=root / "raw.png", cover_publish_path=root / "cover.png", cover_hd_path=root / "hd.png", meta_path=root / "meta.json", caption_path=root / "caption.txt", review_path=root / "review.json")
            topic = TopicRecord(topic_id="topic_1", batch_id="batch_1", topic="雨夜回家", audience="听众", mood="warm", scene="车站", style_hint="pop", publish_platform="douyin")
            caption = build_caption(song, topic)
            self.assertIn("《夜路》", caption)
            self.assertNotIn("锟", caption)


class AudioProfileTests(unittest.TestCase):
    def test_short_video_audio_constraints_are_not_skipped(self):
        constraints = audio_constraints("short_video", "douyin")
        self.assertEqual(constraints["max_intro_seconds"], 3.0)
        self.assertEqual(constraints["min_duration_seconds"], 20.0)

    def test_music_platform_keeps_longform_constraints(self):
        constraints = audio_constraints("music_platform", "qishui_music")
        self.assertEqual(constraints["max_intro_seconds"], 15.0)
        self.assertEqual(constraints["min_duration_seconds"], 165.0)


class LocalLyricsTests(unittest.TestCase):
    def test_local_composer_uses_brief_without_external_provider(self):
        topic = TopicRecord(topic_id="tp_local", batch_id="batch", topic="small happiness", audience="listeners", mood="sweet", scene="cafe", style_hint="pop", publish_platform="qishui_music", distribution_target="music_platform", user_need="a complete song", core_conflict="ordinary days feel too small", unique_observation="the cup handle faces the usual side", emotional_payoff="ordinary becomes sweet", visual_scene="two cups by a window")
        lyrics = compose_local_lyrics(topic)
        self.assertIn("[Chorus]", lyrics)
        self.assertIn("[Verse 2]", lyrics)
        self.assertNotIn("小小幸福", lyrics)
        self.assertIn("[Bridge]", lyrics)
        self.assertEqual(select_local_title(topic), "small happiness")


if __name__ == "__main__":
    unittest.main()
