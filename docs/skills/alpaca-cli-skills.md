# Alpaca CLI skills — read-only extensions (AGENT-SKILLS-C2)

Admin and advisor data exposure only. **No paper submit.** **No `.env` display.** **No `--live`.** Exit code **2** = auth failure → stop.

Canonical script: [`scripts/alpaca_fetch.py`](../../scripts/alpaca_fetch.py) (read-only chain staging wrapper over the greeks layer). Related operator scripts: `scripts/orb_morning_loop.py`, `scripts/operator_status.py`.

Paper transport stays on the repo paper bridge host only on dedicated paper packets—not these CLIs.

## Admin skills (CLI, read-only)

| Script | Flag | Purpose |
|--------|------|---------|
| `alpaca_fetch.py` | `--dte-range 0 3` | Narrow fetch to 0–3 DTE (0DTE-focused chain) |
| `alpaca_fetch.py` | `--delta-filter 0.30 0.55` | Keep contracts in delta band before EV work |
| `operator_status.py` | `--ideas-summary` | Count `PROPOSE` / `WATCH` / `PASS` from latest idea cycle |

Credential check: `--env-check` on greeks staging (exit 1 on missing creds; treat broker auth failures as stop).

## Advisor skills (data only, no transport)

| Data point | Source | How surfaced |
|------------|--------|--------------|
| Quote age | `scripts/alpaca_fetch.py` chain JSON | `quote_age_seconds` when quote timestamp present |
| OI by strike | Run context + hydration expressions (manifest paths) | `open_interest` / `chain_highest_oi_strike` on context row; strike-level OI on expression or fetch rows—flag thin OI in advisor memo only |
| Implied move vs. spread cost | SpotGamma staged context + chain snapshot | reverse-VRP idea #3 ratio in `data_basis` |

**Out of scope for post-ORB advisory:** `examples/alpaca_blueprint_replay_inputs.py`, `examples/alpaca_replay_input_availability.py`, and `docs/alpaca-blueprint-replay.md` are **backtest / C4A planning** only—not the morning operator path. Do not route claude-advisor or Tier 3 idea skills to those scripts unless the coordinator packet explicitly scopes SG-BT replay.

## Redlines

- No `.env` shared or printed via CLI.
- No live Alpaca trade API host in skill docs or fetch wrappers (see `docs/alpaca-paper-bridge.md`).
- No subagent votes bypassing gate sequence.
- Ideas and CLI outputs are advisory inputs only.
