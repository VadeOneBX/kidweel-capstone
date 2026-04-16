# Decision System - Constraint-Based Options Framework

Deterministic decision infrastructure for options trading, with a probabilistic context layer.

---

## Core Principle

> Claude operates as a pre-execution reliability gate.
> It does not select trades, size positions, or execute orders.

The system remains fully deterministic.

Claude evaluates when market structure invalidates otherwise valid setups.

---

## Constraint-Based Design

A Waymo vehicle does not "figure out" how to drive each time it encounters the road.

It operates within strict constraints:
- lane boundaries
- obstacle detection
- right-of-way rules
- safety thresholds

Markets behave similarly.

They are not predictable-but they are constrained.

This system enforces those constraints explicitly:
- playbooks define allowable structures
- risk rules define acceptable outcomes
- deterministic gates enforce consistency

Claude evaluates when those constraints degrade.

The system does not predict.

It enforces boundaries.

---

## Key Finding (C13 - Initial Result)

```
Baseline:
Trades: 11
PF: 1.12
Sharpe: 0.05

Exclude materially changed contexts:
Trades: 8
PF: 5.00
Sharpe: 0.64
```

Claude did not improve trades.

Claude identified when the environment degraded them.

> Results shown are from a limited sample (n=11) and demonstrate structural impact.
> Ongoing runs expand sample size for robustness.

---

## Repository Navigation

<p>
  <a href="./docs/claude-backtest-wiring.md">
    <img src="https://img.shields.io/badge/Claude%20Context-Backtest%20Wiring-black?style=for-the-badge">
  </a>
  <a href="./docs/claude-overlay.md">
    <img src="https://img.shields.io/badge/Claude-Overlay%20Model-black?style=for-the-badge">
  </a>
  <a href="./docs/claude-overlay-testing.md">
    <img src="https://img.shields.io/badge/Overlay-Testing%20Framework-black?style=for-the-badge">
  </a>
  <a href="./diagrams/">
    <img src="https://img.shields.io/badge/Architecture-Diagrams-black?style=for-the-badge">
  </a>
</p>

---

## System Flow

```
Candidate Ingestion -> Screening -> Constraint Layer -> Structure -> Risk -> Backtest -> Evidence

                                          v

                               Claude Context Layer
                         (pre-execution reliability gate)

                                          v

                                Research Comparison
```

---

## Positioning

This is not an AI trading bot.

This is a deterministic decision system with a probabilistic context filter.

---

## Status

- Paper-only system
- Research-first development
- No live execution
