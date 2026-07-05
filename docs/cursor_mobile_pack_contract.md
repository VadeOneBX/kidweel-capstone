# Cursor Mobile Pack Contract

**Cursor mobile** is the mobile implementation/review surface for Cursor agents: scoped repo edits and diff review in coordinator packets. It is not the operator runtime boundary and does not approve, submit, or bypass gates.

Future Cursor mobile packs may use the runtime layer only through explicit surfaces below. **Claude mobile** is a separate review surface (artifact visibility); it does not share Cursor mobile's repo-edit scope unless a coordinator packet says otherwise.

Taxonomy: [CLAUDE.md](../CLAUDE.md#surface-taxonomy-authority-matters).

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
