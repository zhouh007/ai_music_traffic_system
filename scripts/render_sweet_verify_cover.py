from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    song_dir = Path(sys.argv[1])
    size = 1440
    image = Image.new("RGB", (size, size), (247, 218, 190))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / size
        draw.line((0, y, size, y), fill=(247 - int(12 * ratio), 218 - int(8 * ratio), 190 - int(3 * ratio)))
    draw.ellipse((180, 190, 1260, 1270), fill=(255, 239, 216), outline=(184, 121, 92), width=8)
    draw.ellipse((320, 360, 610, 650), fill=(214, 157, 115), outline=(150, 92, 70), width=6)
    draw.ellipse((830, 360, 1120, 650), fill=(229, 178, 132), outline=(150, 92, 70), width=6)
    draw.arc((305, 345, 625, 690), 270, 90, fill=(150, 92, 70), width=18)
    draw.arc((815, 345, 1135, 690), 90, 270, fill=(150, 92, 70), width=18)
    for x in (450, 960):
        draw.arc((x - 55, 240, x + 55, 420), 180, 360, fill=(255, 250, 238), width=7)
    draw.line((720, 720, 720, 1100), fill=(184, 121, 92), width=8)
    draw.ellipse((560, 1030, 880, 1120), fill=(255, 250, 238), outline=(184, 121, 92), width=7)
    title_font = _font(82, bold=True)
    subtitle_font = _font(30)
    title = "Ordinary Turns Sweet"
    draw.text((145, 1165), title, font=title_font, fill=(90, 56, 48))
    draw.text((150, 1270), "SMALL HAPPINESS SINGLES  /  AI MUSIC", font=subtitle_font, fill=(150, 92, 70))
    image.save(song_dir / "cover_raw.png", format="PNG")
    image.save(song_dir / "cover_publish.png", format="PNG")
    image.resize((3000, 3000), Image.Resampling.LANCZOS).save(song_dir / "cover_hd.jpg", format="JPEG", quality=95)


def _font(size: int, bold: bool = False):
    names = ["C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf"]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
