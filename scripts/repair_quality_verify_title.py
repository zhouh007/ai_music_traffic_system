from __future__ import annotations

import json
from pathlib import Path


SONG_DIR = Path(__file__).resolve().parents[1] / "data" / "songs" / "song_quality_verify_001"
TITLE = "".join(chr(code) for code in (0x5E26, 0x7740, 0x665A, 0x98CE, 0x56DE, 0x5BB6))


def main() -> None:
    (SONG_DIR / "title_selected.txt").write_text(TITLE, encoding="utf-8")
    song_path = SONG_DIR / "song.json"
    song = json.loads(song_path.read_text(encoding="utf-8"))
    song["title"] = TITLE
    song["error_message"] = ""
    song_path.write_text(json.dumps(song, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path = SONG_DIR / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["title"] = TITLE
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    caption_suffix = "".join(chr(code) for code in (0xFF1A, 0x7ED9, 0x4E0B, 0x73ED, 0x540E, 0x8FD8, 0x5728, 0x72B9, 0x8C6B, 0x7684, 0x4EBA, 0xFF0C, 0x4E00, 0x9996, 0x5E26, 0x7740, 0x665A, 0x98CE, 0x56DE, 0x5BB6, 0x7684, 0x6B4C, 0x3002))
    tags = "".join(chr(code) for code in (0x97F3, 0x4E50))
    (SONG_DIR / "caption.txt").write_text(f"{TITLE}{caption_suffix}\n#AI{tags}", encoding="utf-8")


if __name__ == "__main__":
    main()
