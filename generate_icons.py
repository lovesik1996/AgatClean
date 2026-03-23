#!/usr/bin/env python3
"""
Generuje ikonę AgatClean (1024x1024) i splash screen (2732x2732)
jako pliki PNG do użycia z @capacitor/assets.

Użycie:
    python generate_icons.py

Wyniki:
    assets/icon.png        – ikona aplikacji 1024x1024
    assets/splash.png      – splash screen 2732x2732
    static/icons/icon-*.png – ikony PWA (72, 96, 128, 144, 152, 192, 384, 512)
"""

import os
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow nie jest zainstalowany. Uruchom: pip install Pillow")
    raise

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
ICONS_DIR  = os.path.join(os.path.dirname(__file__), "static", "icons")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(ICONS_DIR,  exist_ok=True)


def draw_logo(draw: ImageDraw.Draw, x: int, y: int, size: int, bg: str = "#1a73e8") -> None:
    """Rysuje logo AgatClean – prostokąt z ikoną listy."""
    radius = size * 12 // 64
    draw.rounded_rectangle([x, y, x + size, y + size], radius=radius, fill=bg)

    bar_color = "white"
    bar_h = size * 7 // 64
    bar_x1 = x + size * 14 // 64
    bar_x2 = x + size - size * 14 // 64
    bar_x2_short = x + size * 42 // 64
    bar_x2_shorter = x + size * 34 // 64

    bar_r = bar_h // 3
    y1 = y + size * 18 // 64
    y2 = y + size * 31 // 64
    y3 = y + size * 44 // 64

    draw.rounded_rectangle([bar_x1, y1, bar_x2, y1 + bar_h], radius=bar_r, fill=bar_color)
    draw.rounded_rectangle([bar_x1, y2, bar_x2_short, y2 + bar_h], radius=bar_r, fill=bar_color)
    draw.rounded_rectangle([bar_x1, y3, bar_x2_shorter, y3 + bar_h], radius=bar_r, fill=bar_color)


def create_icon(size: int, output_path: str) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_logo(draw, 0, 0, size)
    img.save(output_path, "PNG")
    print(f"  ✓ {output_path}  ({size}x{size})")


def create_splash(width: int, height: int, output_path: str) -> None:
    img = Image.new("RGB", (width, height), "#f7faf9")
    draw = ImageDraw.Draw(img)

    logo_size = min(width, height) // 4
    lx = (width  - logo_size) // 2
    ly = (height - logo_size) // 2 - logo_size // 4
    draw_logo(draw, lx, ly, logo_size)

    img.save(output_path, "PNG")
    print(f"  ✓ {output_path}  ({width}x{height})")


if __name__ == "__main__":
    print("Generowanie ikony aplikacji (1024x1024)...")
    create_icon(1024, os.path.join(ASSETS_DIR, "icon.png"))

    print("Generowanie splash screen (2732x2732)...")
    create_splash(2732, 2732, os.path.join(ASSETS_DIR, "splash.png"))

    print("Generowanie ikon PWA...")
    pwa_sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    for s in pwa_sizes:
        create_icon(s, os.path.join(ICONS_DIR, f"icon-{s}.png"))

    print("\nGotowe! Następny krok:")
    print("  npm run icons")
    print("  npx cap sync")
