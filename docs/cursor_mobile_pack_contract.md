# Cursor Mobile Pack Contract

Future Cursor packs may use the runtime layer only through explicit surfaces.

## Allowed

- Add read-only status endpoints.
- Add dry-run trigger names.
- Publish audit events to Redis.
- Publish mobile notification candidates.
- Add tests for new endpoint behavior.
- Add docs showing operator command paths.

## Not Allowed

- Hidden execution loops.
- Live order routes.
- Gate bypass routes.
- Automatic WATCH promotion.
- Credential exposure.
- Tailscale-required tests.
- LLM-selected trade execution.

## Required Pattern

Every new mobile action must declare:

- route or CLI command
- owner
- receiver
- dry-run behavior
- risk boundary
- audit artifact
- rollback command
