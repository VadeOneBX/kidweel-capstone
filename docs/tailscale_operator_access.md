# Tailscale Operator Access

## Purpose

Tailscale may be used to reach the local Kidweel **runtime command boundary** from a phone (host shell, QOPS API health/status, artifact paths).

Tailscale is optional. The repo must run without it.

## Surfaces (mobile)

| Surface | Role on Tailscale path |
|---------|------------------------|
| **Operator** (phone browser / SSH) | Read `/health`, `/status`, dry-run triggers; SSH to run canonical commands |
| **Claude mobile** | Artifact review only—no execution unless future allowlisted boundary matches desktop |
| **Cursor mobile** | Scoped repo edit/diff review for Cursor agents—no approve, submit, or arbitrary shell |

See [CLAUDE.md](../CLAUDE.md#surface-taxonomy-authority-matters).

## Boundary

Tailscale provides network access only.

It does not:

- approve trades
- submit orders
- bypass gates
- alter paper-only mode
- give Claude.ai, Claude mobile, claude-advisor, Cursor mobile, or any advisory agent execution authority

## Suggested Use

- Mac runs OrbStack and Docker Compose.
- qops-api binds to local port 8000.
- Tailscale exposes the Mac to the operator's phone.
- Mobile browser can check `/health`, `/status`, and bus inspection routes.

## Safe Mobile Routes

- `GET /health`
- `GET /status`
- `GET /bus/{topic}`
- `POST /trigger` with `dry_run: true`

## Unsafe / Forbidden Routes

The repo must not add mobile routes that:

- submit live orders
- approve WATCH candidates
- disable paper-only mode
- change risk caps
- write broker credentials
