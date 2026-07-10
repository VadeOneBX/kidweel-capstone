"""Export the Kidweel LinkedIn HITL carousel mockup to 1080x1350 PNG panels.

Renders each `.panel` in kidweel-site/linkedin-carousel/source.html in
isolation via Playwright/Chromium at native resolution (no raster upscaling)
and verifies output dimensions with Pillow, failing loudly on any mismatch.

Usage:
    pip install playwright pillow
    python scripts/export_kidweel_carousel.py

Chromium must already be installed (this environment provides it at
/opt/pw-browsers/chromium) -- this script does not run `playwright install`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "kidweel-site" / "linkedin-carousel" / "source.html"
CHROMIUM_EXECUTABLE = "/opt/pw-browsers/chromium"
PANEL_COUNT = 6

ISOLATE_PANEL_JS = """(idx) => {
  document.body.classList.add('export-mode');
  document.querySelectorAll('.slide-wrap').forEach((el, i) => {
    el.style.display = (i === idx) ? '' : 'none';
  });
}"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1350)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    source_path = args.source.resolve()
    if not source_path.is_file():
        print(f"ERROR: source HTML not found: {source_path}", file=sys.stderr)
        return 1

    out_dir = (args.out_dir or source_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

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
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        page.goto(f"file://{source_path}")

        for idx in range(PANEL_COUNT):
            page.evaluate(ISOLATE_PANEL_JS, idx)
            page.wait_for_timeout(50)
            out_path = out_dir / f"panel-{idx + 1:02d}.png"
            page.screenshot(path=str(out_path))
            output_paths.append(out_path)

        browser.close()

    mismatches: list[str] = []
    for path in output_paths:
        with Image.open(path) as img:
            size = img.size
        if size != (args.width, args.height):
            mismatches.append(f"{path}: got {size}, expected {(args.width, args.height)}")

    if mismatches:
        print("ERROR: dimension mismatch on exported panels:", file=sys.stderr)
        for line in mismatches:
            print(f"  {line}", file=sys.stderr)
        return 1

    print(f"Exported {len(output_paths)} panels at {args.width}x{args.height}:")
    for path in output_paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
