from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    song_dir = Path(sys.argv[1])
    size = 1440
    image = Image.new("RGB", (size, size), (18, 28, 42))
    draw = ImageDraw.Draw(image)

    # A restrained rainy bus-window composition matching the verification brief.
    for y in range(size):
        ratio = y / size
        color = (18 + int(18 * ratio), 28 + int(22 * ratio), 42 + int(28 * ratio))
        draw.line((0, y, size, y), fill=color)
    for x in range(-200, size + 200, 95):
        draw.line((x, 0, x - 250, size), fill=(70, 100, 124), width=5)
    draw.rectangle((105, 110, 1335, 1330), outline=(174, 197, 205), width=8)
    draw.line((720, 110, 720, 1330), fill=(134, 161, 174), width=4)
    draw.line((105, 840, 1335, 840), fill=(134, 161, 174), width=4)
    draw.ellipse((520, 250, 920, 650), outline=(190, 205, 201), width=6)
    draw.line((720, 650, 720, 1080), fill=(190, 205, 201), width=6)
    draw.line((600, 1080, 840, 1080), fill=(190, 205, 201), width=6)

    title_font = _font(78, bold=True)
    subtitle_font = _font(32)
    title = "带着晚风回家"
    draw.text((130, 1170), title, font=title_font, fill=(241, 239, 225))
    draw.text((136, 1270), "NIGHT ROUTE NOTES  /  AI MUSIC", font=subtitle_font, fill=(169, 198, 201))

    raw = song_dir / "cover_raw.png"
    publish = song_dir / "cover_publish.png"
    hd = song_dir / "cover_hd.jpg"
    image.save(raw, format="PNG")
    image.save(publish, format="PNG")
    image.resize((3000, 3000), Image.Resampling.LANCZOS).save(hd, format="JPEG", quality=95)


def _font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
