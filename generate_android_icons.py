#!/usr/bin/env python3
"""
Generuje Android launcher icons (PNG) dla AgatClean.

Tworzy w każdym katalogu mipmap-*:
  - ic_launcher_background.png  – jednolite tło #2196F3
  - ic_launcher_foreground.png  – biały symbol iskierki, tło przezroczyste
  - ic_launcher_round.png       – okrągła ikona (tło + symbol)
  - ic_launcher.png             – kwadratowa ikona (tło + symbol)

Dodatkowo zapisuje plik bazowy 512x512 do assets/icon_android.png.

Użycie:
    pip install Pillow
    python generate_android_icons.py
"""

import os
import math

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow nie jest zainstalowany. Uruchom: pip install Pillow")
    raise

# ---------------------------------------------------------------------------
# Kolory
# ---------------------------------------------------------------------------
BLUE = (33, 150, 243, 255)       # #2196F3
WHITE = (255, 255, 255, 255)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANDROID_RES = os.path.join(BASE_DIR, "android", "app", "src", "main", "res")

# ---------------------------------------------------------------------------
# Rozmiary ikon tradycyjnych (launcher icon) – px dla każdej gęstości
# ---------------------------------------------------------------------------
LAUNCHER_SIZES = {
    "mipmap-mdpi":    48,
    "mipmap-hdpi":    72,
    "mipmap-xhdpi":   96,
    "mipmap-xxhdpi":  144,
    "mipmap-xxxhdpi": 192,
}

# ---------------------------------------------------------------------------
# Rozmiary warstw adaptive icon (108 dp × scale)
# ---------------------------------------------------------------------------
ADAPTIVE_SIZES = {
    "mipmap-mdpi":    108,
    "mipmap-hdpi":    162,
    "mipmap-xhdpi":   216,
    "mipmap-xxhdpi":  324,
    "mipmap-xxxhdpi": 432,
}


# ---------------------------------------------------------------------------
# Rysowanie symbolu
# ---------------------------------------------------------------------------

def _sparkle_points(cx, cy, outer_r, inner_r, tips=4):
    """Zwraca listę wierzchołków wielokąta tworzącego iskierkę (n-punktową gwiazdę)."""
    pts = []
    for i in range(tips * 2):
        angle = math.pi * i / tips - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def draw_symbol(draw: ImageDraw.ImageDraw, size: int, color=WHITE) -> None:
    """
    Rysuje symbol czystości: duża 4-punktowa iskierka w centrum
    + mała iskierka w prawym górnym rogu + mikro iskierka w lewym dolnym.
    """
    cx, cy = size / 2, size / 2

    # Główna iskierka (centrum)
    outer = size * 0.275
    inner = size * 0.085
    draw.polygon(_sparkle_points(cx, cy, outer, inner, tips=4), fill=color)

    # Mała iskierka (prawy górny)
    s_outer = size * 0.105
    s_inner = size * 0.034
    sx = cx + size * 0.245
    sy = cy - size * 0.215
    draw.polygon(_sparkle_points(sx, sy, s_outer, s_inner, tips=4), fill=color)

    # Mikro iskierka (lewy dolny)
    m_outer = size * 0.065
    m_inner = size * 0.022
    mx = cx - size * 0.225
    my = cy + size * 0.230
    draw.polygon(_sparkle_points(mx, my, m_outer, m_inner, tips=4), fill=color)


# ---------------------------------------------------------------------------
# Tworzenie poszczególnych typów plików
# ---------------------------------------------------------------------------

def create_background_png(size: int, output_path: str) -> None:
    """Jednolite tło #2196F3 (RGB, bez kanału alfa)."""
    img = Image.new("RGB", (size, size), (BLUE[0], BLUE[1], BLUE[2]))
    img.save(output_path, "PNG", optimize=True)
    print(f"  ✓ {os.path.relpath(output_path, BASE_DIR)}")


def create_foreground_png(size: int, output_path: str) -> None:
    """Przezroczyste tło + biały symbol."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_symbol(draw, size)
    img.save(output_path, "PNG", optimize=True)
    print(f"  ✓ {os.path.relpath(output_path, BASE_DIR)}")


def create_round_png(size: int, output_path: str) -> None:
    """Pełna okrągła ikona: niebieskie kółko + biały symbol."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size - 1, size - 1], fill=BLUE)
    draw_symbol(draw, size)
    img.save(output_path, "PNG", optimize=True)
    print(f"  ✓ {os.path.relpath(output_path, BASE_DIR)}")


def create_square_png(size: int, output_path: str) -> None:
    """Pełna kwadratowa ikona z zaokrąglonymi rogami + biały symbol."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(size // 6, 2)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BLUE)
    draw_symbol(draw, size)
    img.save(output_path, "PNG", optimize=True)
    print(f"  ✓ {os.path.relpath(output_path, BASE_DIR)}")


# ---------------------------------------------------------------------------
# Główna logika
# ---------------------------------------------------------------------------

def main():
    # --- Warstwy adaptive icon (background + foreground) ---
    print("\n[1/3] Warstwy adaptive icon (ic_launcher_background / foreground)...")
    for density, size in ADAPTIVE_SIZES.items():
        dir_path = os.path.join(ANDROID_RES, density)
        os.makedirs(dir_path, exist_ok=True)
        create_background_png(size, os.path.join(dir_path, "ic_launcher_background.png"))
        create_foreground_png(size, os.path.join(dir_path, "ic_launcher_foreground.png"))

    # --- Tradycyjne ikony launchera (kwadratowe + okrągłe) ---
    print("\n[2/3] Tradycyjne ikony launchera (ic_launcher + ic_launcher_round)...")
    for density, size in LAUNCHER_SIZES.items():
        dir_path = os.path.join(ANDROID_RES, density)
        os.makedirs(dir_path, exist_ok=True)
        create_square_png(size, os.path.join(dir_path, "ic_launcher.png"))
        create_round_png(size, os.path.join(dir_path, "ic_launcher_round.png"))

    # --- Plik bazowy 512x512 ---
    print("\n[3/3] Plik bazowy 512x512...")
    assets_dir = os.path.join(BASE_DIR, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    create_square_png(512, os.path.join(assets_dir, "icon_android_512.png"))
    create_round_png(512, os.path.join(assets_dir, "icon_android_round_512.png"))

    print("\n✅ Gotowe! Wygenerowano ikony PNG dla wszystkich gęstości.")
    print("   Następne kroki:")
    print("     npx cap sync")
    print("   lub otwórz Android Studio i wybierz Build → Clean Project.")


if __name__ == "__main__":
    main()
