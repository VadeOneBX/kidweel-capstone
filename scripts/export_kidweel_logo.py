"""Export Kidweel logo direction B (Bracket Frame Mark) raster assets.

Renders kidweel-site/logo/export-source.html with Playwright/Chromium,
screenshots each named element at its native pixel size, verifies exact
dimensions with Pillow, and builds a multi-size favicon.ico. No raster
upscaling -- every element is laid out in the DOM at its true target size.

export-source.html is a tracked repo file (not under the ignored build/
directory) so a fresh clone can regenerate every PNG/ICO asset below
without any missing local-only input.

Usage:
    pip install playwright pillow
    python scripts/export_kidweel_logo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "kidweel-site" / "logo" / "export-source.html"
OUT_DIR = REPO_ROOT / "kidweel-site" / "logo"
CHROMIUM_EXECUTABLE = "/opt/pw-browsers/chromium"

# id -> (output filename, expected (width, height))
TARGETS = {
    "dark-bg": ("kidweel-mark-dark-bg.png", (512, 512)),
    "favicon-64": ("favicon-64.png", (64, 64)),
    "favicon-32": ("favicon-32.png", (32, 32)),
    "favicon-16": ("favicon-16.png", (16, 16)),
    "linkedin-profile": ("kidweel-linkedin-profile.png", (400, 400)),
    "github-header": ("kidweel-github-header.png", (1280, 320)),
}


def main() -> int:
    if not SOURCE.is_file():
        print(f"ERROR: source not found: {SOURCE}", file=sys.stderr)
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright is not installed. Run: pip install playwright", file=sys.stderr)
        return 1

    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is not installed. Run: pip install pillow", file=sys.stderr)
        return 1

    output_paths: list[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM_EXECUTABLE)
        page = browser.new_page(viewport={"width": 1400, "height": 1400})
        page.goto(f"file://{SOURCE}")
        page.wait_for_timeout(200)

        for element_id, (filename, _) in TARGETS.items():
            out_path = OUT_DIR / filename
            page.locator(f"#{element_id}").screenshot(path=str(out_path))
            output_paths.append(out_path)

        browser.close()

    mismatches: list[str] = []
    for element_id, (filename, expected) in TARGETS.items():
        path = OUT_DIR / filename
        with Image.open(path) as img:
            size = img.size
        if size != expected:
            mismatches.append(f"{filename}: got {size}, expected {expected}")

    if mismatches:
        print("ERROR: dimension mismatch on exported logo assets:", file=sys.stderr)
        for line in mismatches:
            print(f"  {line}", file=sys.stderr)
        return 1

    # Build favicon.ico from the three favicon PNGs.
    ico_path = OUT_DIR / "favicon.ico"
    with Image.open(OUT_DIR / "favicon-64.png") as base:
        base = base.convert("RGBA")
        base.save(
            ico_path,
            format="ICO",
            sizes=[(16, 16), (32, 32), (64, 64)],
        )
    output_paths.append(ico_path)

    print(f"Exported {len(output_paths)} logo assets:")
    for path in output_paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
