# Kidweel Design Tokens

Direction: **B — Bracket Frame Mark**, visual system **1b — Human Authority Layer**.

## Color

| Token | Value | Use |
|---|---|---|
| `--bg-page` | `#07090b` | Outer page background |
| `--bg-panel` | `#0f1215` | Card / panel background |
| `--bg-panel-2` | `#14181c` | Nested tile background |
| `--line` | `#232a2e` | Panel borders, dividers |
| `--line-bright` | `#2f383d` | Bracket strokes, flow connectors |
| `--white` | `#f2f4f5` | Primary type |
| `--gray` | `#8b959b` | Secondary type |
| `--gray-dim` | `#5a6469` | Tertiary / muted labels |
| `--teal` | `#3fd9c7` | Restrained accent — reserved for the human-authority layer and the decision point in any flow |
| `--teal-dim` | `#1f4b47` | Inactive/secondary teal (e.g. unselected proof bullets) |

Teal is rationed: it marks the **human authority / decision layer** only. It does not decorate generic UI chrome, buttons, or agent-side elements.

## Type

- **Display / body**: Space Grotesk (400/500/600/700)
- **System labels, metadata, mono figures**: IBM Plex Mono (400/500/600)
- Import both via Google Fonts (`family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600`)

## Motifs

- **Blueprint corner brackets** — four `L`-shaped corner marks (1px stroke, `--line-bright`) on any bounded panel. See `components/bracket-card.html`.
- **Human/agent authority line** — a single horizontal rule with `HUMAN` (teal, left) and `AGENTS` (muted gray, right) mono labels. See `components/authority-line.html`.
- **Process flow** — the only approved public flow abstraction: `Agent work → Gate → Human review → Decision → Audit`. `Decision` is the sole teal node. See `components/process-flow.html`.
- Strong negative space; no gradients, no glow/sparkle effects, no robot or agent-swarm imagery.

## Logomark

**B — Bracket Frame Mark**: two corner brackets in 180° rotational symmetry around a single teal dot. Assets in `assets/logo/`.
