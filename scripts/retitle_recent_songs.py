from __future__ import annotations

import json
from pathlib import Path

from ai_music_system.pipeline.cover_renderer import render_publish_covers


TITLE_UPDATES = {
    "song_20260709_218": "等天亮",
    "song_20260709_219": "先抱紧自己",
    "song_20260709_220": "今天先这样吧",
    "song_20260708_217": "迎着风走",
}


def update_song(song_dir: Path, new_title: str) -> None:
    song_path = song_dir / "song.json"
    meta_path = song_dir / "meta.json"
    song_payload = json.loads(song_path.read_text(encoding="utf-8"))
    meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))

    song_payload["title"] = new_title
    meta_payload["title"] = new_title

    song_path.write_text(json.dumps(song_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (song_dir / "title_selected.txt").write_text(new_title, encoding="utf-8")

    render_publish_covers(
        source_path=song_dir / "cover_raw.png",
        publish_path=song_dir / "cover_publish.png",
        hd_path=song_dir / "cover_hd.jpg",
        title=new_title,
        publish_size=1440,
        hd_size=3000,
    )


def main() -> None:
    songs_root = Path(r"F:\code\ai_music_traffic_system\data\songs")
    for song_id, new_title in TITLE_UPDATES.items():
        song_dir = songs_root / song_id
        if not song_dir.exists():
            continue
        update_song(song_dir, new_title)
        print(f"{song_id} -> {new_title}")


if __name__ == "__main__":
    main()
