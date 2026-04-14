# Claude Overlay Testing (C11C)

## Purpose

This document defines the research-only comparison path used to test whether Claude overlay downgrades would have improved backtest outcomes.

## Production boundary

- Claude remains memo-only in production.
- Claude has no proposal rights.
- Claude has no approval rights.
- Claude has no execution rights.

## Research comparison mode

Two deterministic views are computed from the same replay contexts:

- `baseline`: all approved deterministic trades.
- `exclude_downgraded`: counterfactual view that excludes contexts where `overlay.downgrade_flag` is `True`.

This comparison is counterfactual research only. It does not change approval or execution behavior.

## Research variants

The backtest overlay comparison supports these deterministic research modes:

- `baseline`
- `exclude_downgraded`
- `exclude_caution`
- `overlay_only`
- `determined`

These are research-only counterfactual or diagnostic slices. They do not alter production approval or execution behavior.

The `determined` slice isolates trades where the overlay expressed caution or downgrade. It exists to pressure-test whether those flagged contexts cluster weaker outcomes.

Profit factor may display as `INF` when a slice contains gains and zero losses. This is presentation-normalized for readability only; underlying math is unchanged.

## Reported deltas

The overlay comparison reports:

- `trades_removed`
- `net_pnl_change`
- `profit_factor_change`
- `sharpe_change`

These deltas are used to measure whether overlay downgrade signals add value before any future bounded influence is considered.
