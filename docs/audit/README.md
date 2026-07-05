# Audit artifacts (`docs/audit/`)

Committed evidence, mock workflow stages, and **Cursor mobile review bundles**. The repo is the message bus—audit files are durable exports when chat or mobile UI cannot copy conversations reliably.

**Related:** [cursor_mobile_pack_contract.md](../cursor_mobile_pack_contract.md), [workflow-ownership.md](../workflow-ownership.md), [evidence_artifacts_guide.md](../evidence_artifacts_guide.md).

---

## Contents

| Kind | Pattern | Purpose |
|------|---------|---------|
| **Mobile review bundle** | `<packet_slug>_bundle.md` | Packet closeout export for Cursor mobile / GitHub review |
| **Run evidence** | e.g. `paper_bull_call_c1_evidence.md` | Deterministic run records (paths may reference gitignored `data/`) |
| **Mock workflow** | `mock_*_C1.md` | Dry-run handoff / advisory shape examples |

**Exemplar bundle:** [taxonomy_normalization_bundle.md](./taxonomy_normalization_bundle.md)

---

## Cursor mobile review bundle standard

**Rule:** Every **Cursor mobile implementation/review packet** commits a markdown bundle here when chat sharing or export is insufficient.

**Cursor mobile** is an implementation/review surface—not the operator runtime boundary. Bundles document work; they do not approve, submit, bypass gates, or replace canonical shell commands.

### Required fields (section order)

1. **Packet name** — full packet ID  
2. **Branch** — feature branch  
3. **Commit** — hash + message  
4. **PR** — URL or number  
5. **Scope** — what changed (e.g. docs-only)  
6. **Changed files** — table with path, delta, summary  
7. **Acceptance checklist** — criteria with status  
8. **Authority after merge** — canonical doc/path post-merge  
9. **Per-file summary** — one subsection per touched file  
10. **Out-of-scope confirmation** — explicit non-changes (`src/`, scripts, tests, command syntax unless packeted)  
11. **Mobile review path** — how to open on Cursor mobile or GitHub  
12. **Export commands** — host `git diff` / patch one-liners  

### Naming

```text
docs/audit/<packet_slug>_bundle.md
```

Use lowercase hyphenated slugs derived from the packet ID (e.g. `taxonomy-normalization` → `taxonomy_normalization_bundle.md`).

### Closeout checklist

- [ ] Bundle committed on the packet branch before operator review  
- [ ] PR links to the bundle path  
- [ ] Acceptance checklist matches packet scope  
- [ ] Out-of-scope section lists untouched paths  
- [ ] No repo-canonical command syntax changed unless explicitly scoped  
- [ ] Bundle does not claim approval or transport authority  

### What bundles are not

- Not operator runtime commands—see [operator_commands.md](../operator_commands.md)  
- Not claude-advisor handoff responses—see [handoffs/README.md](../handoffs/README.md)  
- Not a substitute for pytest or reconciliation when the packet requires them  
