from __future__ import annotations

import json

from scripts.cleanup_song_artifacts import collect_cleanup_targets


def test_collect_cleanup_targets_preserves_release_outputs(tmp_path):
    song_dir = tmp_path / "song"
    song_dir.mkdir()
    (song_dir / "song.json").write_text(json.dumps({"status": "generated"}), encoding="utf-8")

    keep_names = [
        "audio.mp3",
        "audio_douyin.mp3",
        "audio_douyin_lyrics.txt",
        "cover_publish.png",
        "lyrics_clean.txt",
        "meta.json",
    ]
    for name in keep_names:
        (song_dir / name).write_text("keep", encoding="utf-8")

    removable_names = [
        "audio_validation_attempt_1.json",
        "cover_publish_wrong_title.png",
        "font_test.png",
        "music_response.json",
        "error.json",
    ]
    for name in removable_names:
        (song_dir / name).write_text("remove", encoding="utf-8")

    targets = {path.name for path in collect_cleanup_targets(song_dir, aggressive=True)}

    assert targets == set(removable_names)
