from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def render_publish_covers(
    source_path: Path,
    publish_path: Path,
    hd_path: Path,
    title: str,
    publish_size: int,
    hd_size: int,
) -> None:
    image = Image.open(source_path).convert("RGB")
    publish_image = image.resize((publish_size, publish_size))
    hd_image = image.resize((hd_size, hd_size))

    _draw_title(publish_image, title)
    _draw_title(hd_image, title)

    publish_image.save(publish_path)
    hd_image.save(hd_path, quality=95)


def _draw_title(image: Image.Image, title: str) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    padding = 48
    text_y = image.height - 110
    draw.rectangle((0, image.height - 150, image.width, image.height), fill=(0, 0, 0))
    draw.text((padding, text_y), title, fill=(255, 255, 255), font=font)
