from __future__ import annotations

import unittest

from ai_music_system.cover_strategy import COVER_FAMILIES, build_cover_direction, extract_lyric_imagery
from ai_music_system.models import SongRecord, TopicRecord
from pathlib import Path


class CoverStrategyTests(unittest.TestCase):
    def test_direction_is_stable_and_uses_lyrics(self):
        root = Path("song")
        song = SongRecord(song_id="song_401", topic_id="tp_401", batch_id="batch", title="风吹进来的时候", mode="text_to_music", status="generated", song_dir=root, lyrics_raw_path=root/"raw", lyrics_clean_path=root/"clean", audio_path=root/"audio", cover_raw_path=root/"cover", cover_publish_path=root/"publish", cover_hd_path=root/"hd", meta_path=root/"meta", caption_path=root/"caption", review_path=root/"review")
        topic = TopicRecord(topic_id="tp_401", batch_id="batch", topic="晚风", audience="all", mood="warm", scene="room", style_hint="pop", publish_platform="qishui_music")
        first = build_cover_direction(song, topic, "钥匙落在桌上，窗帘被晚风吹动")
        second = build_cover_direction(song, topic, "钥匙落在桌上，窗帘被晚风吹动")
        self.assertEqual(first, second)
        self.assertIn("钥匙", first["lyric_imagery"])
        self.assertIn(first["cover_family"], [item[0] for item in COVER_FAMILIES])


if __name__ == "__main__":
    unittest.main()
