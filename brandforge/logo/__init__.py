"""Logo generation: monogram SVG + PNG export."""

from __future__ import annotations

import colorsys
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from brandforge.config import LOGOS_DIR


def _palette_from_name(name: str) -> tuple[str, str, str]:
    """Deterministic brand palette from name hash."""
    digest = hashlib.sha256(name.lower().encode()).hexdigest()
    h = int(digest[:8], 16) % 360
    # Prefer teal / slate / forest / rust — skip purple–magenta band
    if 240 <= h <= 320:
        h = (h + 110) % 360
    if 280 <= h <= 330:
        h = (h + 90) % 360

    def hsl(hh: float, s: float, l: float) -> str:
        r, g, b = colorsys.hls_to_rgb(hh / 360.0, l, s)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    primary = hsl(h, 0.62, 0.42)
    accent = hsl((h + 28) % 360, 0.55, 0.55)
    ink = hsl(h, 0.15, 0.12)
    return primary, accent, ink


def logo_prompt(name: str, category: str | None = None) -> str:
    primary, accent, ink = _palette_from_name(name)
    niche = category or "technology startup"
    return (
        f"Minimal wordmark logo for '{name}', a {niche} brand. "
        f"Clean geometric letterforms, no icons cluttering the mark, "
        f"flat vector, generous kerning, colors {primary} and {accent} on "
        f"light paper with {ink} secondary text. No gradients, no 3D, no mockups."
    )


def render_svg(name: str, out_path: Path | None = None) -> Path:
    """Create a simple lettermark + wordmark SVG."""
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    out = out_path or (LOGOS_DIR / f"{name.lower()}.svg")
    primary, accent, ink = _palette_from_name(name)
    initial = name[0].upper()
    word = name

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="512" viewBox="0 0 1024 512" role="img" aria-label="{word} logo">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#f7f4ef"/>
      <stop offset="100%" stop-color="#ebe4d8"/>
    </linearGradient>
  </defs>
  <rect width="1024" height="512" fill="url(#bg)"/>
  <circle cx="220" cy="256" r="110" fill="{primary}"/>
  <circle cx="250" cy="230" r="36" fill="{accent}" opacity="0.85"/>
  <text x="220" y="276" text-anchor="middle" font-family="Georgia, 'Times New Roman', serif"
        font-size="120" font-weight="700" fill="#faf8f5">{initial}</text>
  <text x="400" y="280" font-family="Georgia, 'Times New Roman', serif"
        font-size="92" font-weight="700" fill="{ink}">{word}</text>
  <rect x="400" y="310" width="220" height="6" rx="3" fill="{accent}"/>
</svg>
'''
    out.write_text(svg, encoding="utf-8")
    return out


def render_png(name: str, out_path: Path | None = None, size: tuple[int, int] = (1024, 512)) -> Path:
    """Rasterize a matching PNG wordmark with Pillow."""
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    out = out_path or (LOGOS_DIR / f"{name.lower()}.png")
    primary, accent, ink = _palette_from_name(name)
    w, h = size
    img = Image.new("RGB", (w, h), "#f7f4ef")
    draw = ImageDraw.Draw(img)

    # Soft diagonal wash
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(247 - 12 * t)
        g = int(244 - 16 * t)
        b = int(239 - 23 * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    cx, cy, radius = 220, h // 2, 110
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=primary)
    draw.ellipse((cx + 10, cy - 50, cx + 70, cy + 10), fill=accent)

    try:
        font_big = ImageFont.truetype("arial.ttf", 120)
        font_word = ImageFont.truetype("arial.ttf", 92)
    except OSError:
        try:
            font_big = ImageFont.truetype("C:/Windows/Fonts/georgia.ttf", 120)
            font_word = ImageFont.truetype("C:/Windows/Fonts/georgia.ttf", 92)
        except OSError:
            font_big = ImageFont.load_default()
            font_word = ImageFont.load_default()

    initial = name[0].upper()
    # Center initial roughly in the circle
    bbox = draw.textbbox((0, 0), initial, font=font_big)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw / 2, cy - th / 2 - 8), initial, font=font_big, fill="#faf8f5")
    draw.text((400, cy - 50), name, font=font_word, fill=ink)
    draw.rounded_rectangle((400, cy + 55, 620, cy + 61), radius=3, fill=accent)

    img.save(out, format="PNG")
    return out


def generate_logo_kit(name: str, category: str | None = None) -> dict[str, str]:
    """Write SVG, PNG, and a reusable logo prompt."""
    svg = render_svg(name)
    png = render_png(name)
    prompt = logo_prompt(name, category)
    prompt_path = LOGOS_DIR / f"{name.lower()}.prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    return {
        "svg": str(svg),
        "png": str(png),
        "prompt": str(prompt_path),
        "prompt_text": prompt,
    }
