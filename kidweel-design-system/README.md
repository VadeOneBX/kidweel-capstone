# Kidweel Design System

A narrow, public-safe package of the current Kidweel visual system, prepared for Claude Design `/design-sync`.

**This is a design-sync package only.** It is not a trading-system package and not a repo-wide sync. It contains no execution code, no strategy logic, no private data, and no logs.

## Design anchors

- **B — Bracket Frame Mark** (logomark direction)
- **1b — Human Authority Layer** (visual system)
- Charcoal / white / muted gray / restrained teal
- Space Grotesk (display), IBM Plex Mono (system labels)
- Blueprint corner brackets
- Human/agent authority line
- Process flow: `Agent work → Gate → Human review → Decision → Audit`

See `design-tokens.md` for exact values and `approved-language.md` for approved/avoid copy.

## Structure

```
kidweel-design-system/
├── README.md
├── design-tokens.md
├── approved-language.md
├── components/
│   ├── authority-line.html
│   ├── bracket-card.html
│   ├── process-flow.html
│   └── proof-card.html
└── assets/
    ├── logo/
    │   ├── kidweel-mark.svg
    │   ├── kidweel-lockup.svg
    │   └── favicon-64.png
    ├── carousel/
    │   ├── panel-01.png
    │   └── panel-06.png
    └── splash/
        ├── desktop-preview.png
        └── mobile-preview.png
```

## Run

```bash
cd kidweel-design-system
claude
/design-sync
```

## Scope boundary

Excluded by design: `src/`, `pyproject.toml`, `data/`, `logs/`, any private/broker/execution code, old root agent maps, SpotGamma-specific strategy maps, and any other vendor/private workflow artifacts. If a future sync needs more than this package contains, that's a new, explicitly-scoped packet — not an expansion of this one.
