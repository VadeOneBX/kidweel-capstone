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

## Mobile review bundle (required for implementation/review packs)

Cursor mobile has **no reliable chat export** for cloud-agent conversations. When chat sharing or copy is insufficient, every **Cursor mobile implementation/review packet** must commit a markdown bundle under `docs/audit/`.

**Rule:** The bundle is the authoritative packet export—not chat screenshots or pasted thread text.

**Naming:** `docs/audit/<packet_slug>_bundle.md` (lowercase, hyphenated slug). Example: [taxonomy_normalization_bundle.md](./audit/taxonomy_normalization_bundle.md).

**When required:** Any Cursor mobile pack that changes repo files and expects operator review on mobile or GitHub without IDE chat access.

**When optional:** Read-only visibility checks with no committed diff (e.g. dry-run `/health` only)—still recommended if the operator needs a closeout record.

### Required bundle fields

Every bundle must include these sections (in order):

| Field | Content |
|-------|---------|
| **Packet name** | Full packet ID / title |
| **Branch** | Feature branch name |
| **Commit** | Hash + message for the primary packet commit |
| **PR** | Link or number |
| **Scope** | What changed; explicit docs-only / code paths |
| **Changed files** | Table: path, delta, one-line summary |
| **Acceptance checklist** | Packet criteria with pass/fail |
| **Authority after merge** | Which doc or path is canonical when the PR lands |
| **Per-file summary** | Short subsection per touched file |
| **Out-of-scope confirmation** | What was **not** changed (e.g. no `src/`, no command syntax) |
| **Mobile review path** | Steps to open the bundle on Cursor mobile or GitHub |
| **Export commands** | Host `git diff` / patch commands for offline archive |

### Authority boundary (bundle does not)

- Replace operator runtime commands (`uv run`, `orb_morning_loop.py`, etc.)
- Approve, size, submit, bypass gates, or run arbitrary shell from mobile chat
- Change repo-canonical command syntax unless a separate scoped packet allows it

**Cursor mobile** remains an **implementation/review surface** only. The bundle documents work; the **operator runtime boundary** executes commands.

See [audit/README.md](./audit/README.md) for directory conventions and [workflow-ownership.md](./workflow-ownership.md#cursor-mobile-review-bundles).
