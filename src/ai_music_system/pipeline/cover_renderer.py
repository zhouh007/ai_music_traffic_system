from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat


FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/NotoSerifSC-VF.ttf"),
    Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
]


def render_publish_covers(source_path: Path, publish_path: Path, hd_path: Path, title: str, publish_size: int, hd_size: int) -> None:
    image = Image.open(source_path).convert("RGB")
    publish_image = image.resize((publish_size, publish_size), Image.Resampling.LANCZOS)
    hd_image = image.resize((hd_size, hd_size), Image.Resampling.LANCZOS)
    _draw_title(publish_image, title)
    _draw_title(hd_image, title)
    publish_image.save(publish_path)
    hd_image.save(hd_path, quality=95)


def _draw_title(image: Image.Image, title: str) -> None:
    title = title.strip()
    if not title:
        return
    draw = ImageDraw.Draw(image)
    font_path = next((path for path in FONT_CANDIDATES if path.exists()), None)
    if font_path is None:
        raise FileNotFoundError("No CJK cover font found.")
    font_size = max(42, round(image.width * (0.068 if len(title) <= 8 else 0.056)))
    font = ImageFont.truetype(str(font_path), font_size)
    margin = round(image.width * 0.065)
    max_width = round(image.width * 0.62)
    lines = _wrap_title(draw, title, font, max_width)
    line_gap = round(font_size * 0.22)
    heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total_height = sum(heights) + line_gap * (len(lines) - 1)
    x = margin
    y = image.height - margin - total_height
    sample = image.crop((0, max(0, y - margin // 2), min(image.width, max_width + margin * 2), image.height))
    luminance = ImageStat.Stat(sample.convert("L")).mean[0]
    fill = (28, 32, 35) if luminance > 145 else (250, 248, 242)
    shadow = (255, 255, 255, 150) if luminance > 145 else (0, 0, 0, 150)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    current_y = y
    stroke = max(1, round(image.width * 0.002))
    for line, height in zip(lines, heights):
        overlay_draw.text((x + stroke, current_y + stroke), line, font=font, fill=shadow)
        overlay_draw.text((x, current_y), line, font=font, fill=fill + (255,))
        current_y += height + line_gap
    image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))


def _wrap_title(draw: ImageDraw.ImageDraw, title: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    if draw.textlength(title, font=font) <= max_width:
        return [title]
    midpoint = (len(title) + 1) // 2
    return [title[:midpoint], title[midpoint:]]
