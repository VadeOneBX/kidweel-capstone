# Kidweel HITL Carousel

LinkedIn carousel artifact for the Kidweel public proof surface.

## Thesis

Agents assist.
Humans decide.
The process records why.

## Format

- 6 panels
- 1080 x 1350 PNG
- LinkedIn carousel-ready
- Static first-pass artifact

## Public posture

This artifact describes bounded delegation for enterprise workflows.

It does not describe autonomous trading, live-money execution, investment advice, or a signal service.

## Caption

Most AI systems make the model louder.

Kidweel tests the opposite posture:

Agents assist.
Humans decide.
The process records why.

This started inside a live paper-trading automation capstone, but the larger proof is portable: bounded delegation for enterprise workflows.

Not autonomous.
Not a signal service.
Not a louder bot.

A sharper process.

## Alt text

Six-panel Kidweel carousel explaining bounded delegation for enterprise workflows. The panels contrast noisy AI automation patterns with a process where agents are always available but never in charge. The sequence shows context moving through candidate, gate, review, decision, and audit steps, ending with the thesis: Agents assist. Humans decide. The process records why.

## Copy note

The packet's Scene 5 text block specified "Selected is still reviewed." The approved `source.html` mockup uses "Designated is still reviewed." instead. The HTML file is the source of truth for this build/export task, so the mockup's wording was kept as-is and no copy was changed. Flagging here for operator awareness.

## Export

Native 1080x1350 panels are rendered via Playwright/Chromium (not screenshots, not upscaling) using `body.export-mode` CSS in `source.html`, which isolates one panel at a time and scales every dimension by the exact preview-to-target factor (1080/380 = 54/19).

Run:

```bash
pip install playwright pillow
python scripts/export_kidweel_carousel.py
```

Chromium must already be installed (this environment provides it at `/opt/pw-browsers/chromium`) — the script does not run `playwright install`.

Optional flags: `--source`, `--out-dir`, `--width`, `--height` (defaults: this directory's `source.html`, this directory, 1080, 1350).

The script verifies each exported PNG is exactly the target dimensions via Pillow and fails loudly (non-zero exit) on any mismatch.
