# Tailscale Operator Access

## Purpose

Tailscale may be used to reach the local Kidweel runtime from mobile.

Tailscale is optional. The repo must run without it.

## Boundary

Tailscale provides network access only.

It does not:

- approve trades
- submit orders
- bypass gates
- alter paper-only mode
- give Claude or any agent execution authority

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
