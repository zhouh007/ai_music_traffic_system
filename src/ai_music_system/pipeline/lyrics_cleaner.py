from __future__ import annotations


def normalize_lyrics(raw_lyrics: str) -> str:
    lines = [line.rstrip() for line in raw_lyrics.splitlines()]
    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not previous_blank:
                cleaned.append("")
            previous_blank = True
            continue
        cleaned.append(stripped.replace("（", "").replace("）", "").replace("(", "").replace(")", ""))
        previous_blank = False
    return "\n".join(cleaned).strip() + "\n"
