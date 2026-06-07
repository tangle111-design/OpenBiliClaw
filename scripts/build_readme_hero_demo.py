#!/usr/bin/env python3
"""Build the README hero demo from local screenshots.

Usage:
  python3 -m pip install Pillow
  python3 scripts/build_readme_hero_demo.py

The script intentionally uses only screenshots already committed under
docs/images/. It produces docs/images/hero-demo.png and, unless disabled,
docs/images/hero-demo.gif for the README first screen.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import wrap

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Pillow is required to build the README hero demo.\n"
        "Install it with: python3 -m pip install Pillow\n"
        "Then rerun: python3 scripts/build_readme_hero_demo.py"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "docs" / "images"
OUTPUT_PNG = IMAGE_DIR / "hero-demo.png"
OUTPUT_GIF = IMAGE_DIR / "hero-demo.gif"

CANVAS = (1280, 720)
PANEL_W = 286
PANEL_H = 452
PANEL_TOP = 198
PANEL_GAP = 18
PANEL_X = 36

BG = "#f8fafc"
INK = "#102033"
MUTED = "#617083"
LINE = "#d8e1ea"
BLUE = "#2563eb"
GREEN = "#16a34a"
ORANGE = "#f97316"
PURPLE = "#7c3aed"
RED = "#dc2626"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Return a readable font across macOS, Linux, and minimal CI images."""
    macos = "/System/Library/Fonts/Supplemental"
    candidates = [
        f"{macos}/Arial Bold.ttf" if bold else f"{macos}/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_TITLE = font(38, bold=True)
FONT_SUBTITLE = font(20)
FONT_PANEL_TITLE = font(23, bold=True)
FONT_SMALL = font(14)
FONT_CHIP = font(15, bold=True)


def text_size(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=face)
    return box[2] - box[0], box[3] - box[1]


def rounded_thumbnail(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        raise SystemExit(f"Missing screenshot: {path}")
    with Image.open(path) as source:
        source = source.convert("RGB")
        thumb = ImageOps.contain(source, size, Image.Resampling.LANCZOS)

    layer = Image.new("RGB", size, "white")
    x = (size[0] - thumb.width) // 2
    y = (size[1] - thumb.height) // 2
    layer.paste(thumb, (x, y))

    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=18, fill=255)
    rounded = Image.new("RGB", size, "white")
    rounded.paste(layer, (0, 0), mask)
    return rounded


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    width_chars: int,
    face: ImageFont.ImageFont,
    fill: str,
    line_gap: int = 5,
) -> int:
    x, y = xy
    for line in wrap(text, width=width_chars):
        draw.text((x, y), line, font=face, fill=fill)
        _, h = text_size(draw, line, face)
        y += h + line_gap
    return y


def draw_chip(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    label: str,
    fill: str,
    text_fill: str = "white",
) -> tuple[int, int]:
    x, y = xy
    w, h = text_size(draw, label, FONT_CHIP)
    pad_x, pad_y = 14, 8
    rect = (x, y, x + w + pad_x * 2, y + h + pad_y * 2)
    draw.rounded_rectangle(rect, radius=16, fill=fill)
    draw.text((x + pad_x, y + pad_y - 1), label, font=FONT_CHIP, fill=text_fill)
    return rect[2], rect[3]


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill: str = LINE) -> None:
    sx, sy = start
    ex, ey = end
    draw.line((sx, sy, ex, ey), fill=fill, width=3)
    draw.polygon([(ex, ey), (ex - 10, ey - 6), (ex - 10, ey + 6)], fill=fill)


def draw_panel(
    base: Image.Image,
    index: int,
    title: str,
    body: str,
    screenshot: Path,
    accent: str,
    active: bool,
    overlay: list[tuple[str, str]],
) -> None:
    draw = ImageDraw.Draw(base)
    x = PANEL_X + index * (PANEL_W + PANEL_GAP)
    y = PANEL_TOP
    border = accent if active else LINE
    width = 4 if active else 2
    fill = "#ffffff" if active else "#fbfdff"

    draw.rounded_rectangle((x, y, x + PANEL_W, y + PANEL_H), radius=24, fill=fill, outline=border, width=width)
    draw.text((x + 20, y + 20), title, font=FONT_PANEL_TITLE, fill=INK)
    draw_wrapped(draw, body, (x + 20, y + 56), 28, FONT_SMALL, MUTED, line_gap=4)

    thumb = rounded_thumbnail(screenshot, (PANEL_W - 38, 246))
    base.paste(thumb, (x + 19, y + 112))
    draw.rounded_rectangle((x + 19, y + 112, x + PANEL_W - 19, y + 358), radius=18, outline="#e5edf5", width=1)

    chip_y = y + 374
    chip_x = x + 20
    for label, color in overlay:
        next_x, next_y = draw_chip(draw, (chip_x, chip_y), label, color)
        chip_x = next_x + 8
        if chip_x > x + PANEL_W - 90:
            chip_x = x + 20
            chip_y = next_y + 8


def build_frame(active: int | None = None) -> Image.Image:
    base = Image.new("RGB", CANVAS, BG)
    draw = ImageDraw.Draw(base)

    draw.text((36, 30), "OpenBiliClaw in 10 seconds", font=FONT_TITLE, fill=INK)
    draw.text(
        (38, 78),
        "Cross-platform signals become a private taste profile, reasoned recommendations, and a feedback loop.",
        font=FONT_SUBTITLE,
        fill=MUTED,
    )

    x, y = 38, 126
    for label, color in [
        ("Bilibili", BLUE),
        ("Xiaohongshu", RED),
        ("Douyin", INK),
        ("YouTube", RED),
        ("Web", PURPLE),
    ]:
        x, _ = draw_chip(draw, (x, y), label, color)
        x += 8
    draw_arrow(draw, (x + 6, y + 16), (x + 74, y + 16), "#94a3b8")
    x += 88
    x, _ = draw_chip(draw, (x, y), "Local backend", GREEN)
    draw_arrow(draw, (x + 12, y + 16), (x + 78, y + 16), "#94a3b8")
    draw_chip(draw, (x + 92, y), "SQLite on your machine", ORANGE)

    panels = [
        (
            "1. Signals in",
            "The extension reads your own logged-in sessions across platforms.",
            IMAGE_DIR / "desktop-home.png",
            BLUE,
            [("sources", BLUE), ("local API", GREEN)],
        ),
        (
            "2. Taste profile",
            "The backend turns behavior into interests, cognitive style, and deep needs.",
            IMAGE_DIR / "desktop-profile.png",
            PURPLE,
            [("interests", PURPLE), ("MBTI", BLUE), ("needs", ORANGE)],
        ),
        (
            "3. Reasons",
            "Cards explain why a video or note fits you instead of saying guess you like.",
            IMAGE_DIR / "desktop-cards.png",
            ORANGE,
            [("why this fits", ORANGE), ("mixed sources", BLUE)],
        ),
        (
            "4. Feedback loop",
            "Like, not interested, and chat feedback tune what comes next.",
            IMAGE_DIR / "mobile-recommend.png",
            GREEN,
            [("Like", GREEN), ("Not interested", RED), ("Chat", PURPLE)],
        ),
    ]

    for idx, (title, body, screenshot, accent, overlay) in enumerate(panels):
        draw_panel(base, idx, title, body, screenshot, accent, active is None or active == idx, overlay)
        if idx < 3:
            arrow_y = PANEL_TOP + PANEL_H // 2
            arrow_x = PANEL_X + idx * (PANEL_W + PANEL_GAP) + PANEL_W + 4
            draw_arrow(draw, (arrow_x, arrow_y), (arrow_x + PANEL_GAP - 4, arrow_y), "#cbd5e1")

    return base


def save_gif(frames: list[Image.Image], output: Path) -> None:
    quantized = [frame.quantize(colors=192) for frame in frames]
    quantized[0].save(
        output,
        save_all=True,
        append_images=quantized[1:],
        duration=1200,
        loop=0,
        optimize=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build README hero demo assets.")
    parser.add_argument("--png-only", action="store_true", help="Only write docs/images/hero-demo.png.")
    args = parser.parse_args()

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    static = build_frame(active=None)
    static.save(OUTPUT_PNG, optimize=True)

    if not args.png_only:
        frames = [build_frame(active=i) for i in range(4)]
        save_gif(frames, OUTPUT_GIF)

    print(f"Wrote {OUTPUT_PNG.relative_to(ROOT)}")
    if not args.png_only:
        print(f"Wrote {OUTPUT_GIF.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
