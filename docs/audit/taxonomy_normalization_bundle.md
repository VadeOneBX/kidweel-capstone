# Taxonomy normalization — diff summary bundle

**Packet:** CURSOR MOBILE TEST PACKET — TAXONOMY NORMALIZATION  
**Commit:** `a41d1ea` — `docs: normalize claude and cursor mobile taxonomy`  
**Branch:** `cursor/taxonomy-normalization-7791`  
**PR:** https://github.com/VadeOneBX/kidweel-capstone/pull/6  
**Scope:** Docs-only (no `src/`, `scripts/`, `tests/` changes)  
**Stats:** 11 files changed, **+102** / **−49**

**Purpose:** Mobile-friendly export of packet results. Open this file on Cursor mobile or GitHub instead of copying chat output. Conforms to [audit/README.md](./README.md) (mobile review bundle standard).

**Canonical authority after merge:** [CLAUDE.md — Surface taxonomy](../CLAUDE.md#surface-taxonomy-authority-matters)

---

## Acceptance checklist

| Criterion | Status |
|-----------|--------|
| Generic "Claude" references disambiguated where authority matters | ✅ |
| Cursor mobile added as distinct implementation/review surface | ✅ |
| Operator docs distinguish runtime command boundary from implementation surfaces | ✅ |
| No src/scripts/tests changes | ✅ |
| Repo-canonical command syntax unchanged | ✅ |
| No execution authority added to mobile surfaces | ✅ |

---

## Canonical taxonomy

| Surface | Role | Does not |
|---------|------|----------|
| **Operator** | Human decision-maker; packet scope, approval, transport opt-in | Delegate authority to mobile or advisory surfaces |
| **Claude.ai desktop** | Operator-facing review; future allowlisted command triggering | Approve, size, submit, bypass gates, arbitrary shell |
| **Claude mobile** | Visibility/review only unless routed through the same allowlisted boundary | Approve, size, submit, bypass gates, arbitrary shell |
| **claude-advisor** | Repo advisory skill/subagent; `ADVISORY_*` labels and memos | Approve, size, submit, transport, gate changes |
| **Claude Code / Cursor Claude** | IDE/coding assistant; scoped repo edits in coordinator packets | Approve, size, submit, transport |
| **Cursor mobile** | Mobile implementation/review for Cursor agents; scoped repo edits and diff review | Approve, size, submit, bypass gates, arbitrary shell |
| **Advisory agents** | Typed review tools (repo-cleaner, safety-auditor, etc.) | Approval, transport, spawn subagents |

**Runtime command boundary:** canonical operator commands (`uv run`, `scripts/orb_morning_loop.py`, `operator_status.py`, etc.) run on the host or via SSH/Tailscale—they are not IDE or mobile chat actions. Implementation surfaces (Cursor, Claude Code, Cursor mobile) edit docs/code; they do not replace the operator runtime path.

**Doctrine change:** "Claude proposes" → **"Advisory proposes"** (claude-advisor, advisory agents). The system decides. Transport executes.

---

## Files changed

| File | Δ | Summary |
|------|---|---------|
| `CLAUDE.md` | +18 / −1 | Surface taxonomy table; runtime boundary note; doctrine wording |
| `AGENTS.md` | +6 / −1 | Taxonomy pointer; doctrine aligned; operator owns delegation |
| `docs/operator_commands.md` | +6 / −0 | Runtime boundary intro; advisory section renamed (brief artifact vs skill) |
| `docs/operator_test_commands_morning_loop.md` | +7 / −1 | Advisory brief vs claude-advisor; expanded boundary reminder |
| `docs/evidence_artifacts_guide.md` | +12 / −3 | Human-determinism table split by surface |
| `docs/tailscale_operator_access.md` | +14 / −1 | Mobile surface table; explicit no-execution list |
| `docs/mobile_infra_runbook.md` | +8 / −2 | Runtime vs implementation surfaces |
| `docs/cursor_mobile_pack_contract.md` | +6 / −1 | Cursor mobile definition; Claude mobile contrast |
| `docs/claude-advisor-context.md` | +6 / −1 | "Not the same as" disambiguation block |
| `docs/workflow-ownership.md` | +62 / −49 | Ownership & tool tables rewritten; operator approval path |
| `docs/kidweel_agents_as_tools_agility_c1.md` | +6 / −2 | Advisory agent + mobile surface boundary note |

---

## Per-file changes

### `CLAUDE.md`

- Doctrine: **Advisory proposes** (claude-advisor, advisory agents)
- **Added** `## Surface taxonomy (authority matters)` table (7 surfaces + runtime boundary paragraph)

### `AGENTS.md`

- Doctrine aligned to advisory proposes
- **Added** surface taxonomy summary with link to `CLAUDE.md#surface-taxonomy-authority-matters`
- Policy #1: **Operator (coordinator) owns delegation**

### `docs/operator_commands.md`

- **Added** surfaces note: commands run on operator runtime boundary, not Claude.ai / Claude mobile / Cursor mobile chat
- Renamed `## View Claude advisory` → `## View advisory brief (deterministic artifact)`
- Clarified: `claude_brief` artifact ≠ claude-advisor skill output

### `docs/operator_test_commands_morning_loop.md`

- Chain step: **Claude brief** → **advisory brief** (`claude_brief` artifact)
- **Added** surfaces paragraph (runtime vs review/implementation)
- Boundary reminder: runtime vs Cursor mobile / Claude Code / Claude.ai; mobile visibility read/dry-run only

### `docs/evidence_artifacts_guide.md`

- Human determinism table: split **Coordinator** → **Operator**; **Claude / claude-advisor** → separate rows for claude-advisor, advisory agents, Claude.ai, Cursor surfaces
- Section B: **Claude advisor skill** → **claude-advisor skill**; distinguishes skill from morning brief artifact

### `docs/tailscale_operator_access.md`

- Purpose: reach **runtime command boundary** from phone
- **Added** mobile surfaces table (operator, Claude mobile, Cursor mobile)
- No-execution list: Claude.ai, Claude mobile, claude-advisor, Cursor mobile, advisory agents

### `docs/mobile_infra_runbook.md`

- Runtime surface ≠ implementation/advisory authority path
- **Cursor mobile** packs (was generic "Cursor packs")
- **Added** surfaces paragraph: QOPS API = runtime boundary; Claude mobile review-only; Cursor mobile scoped edits

### `docs/cursor_mobile_pack_contract.md`

- **Added** Cursor mobile definition (implementation/review for Cursor agents)
- Contrasts **Claude mobile** (artifact visibility, separate scope)
- Links to taxonomy in `CLAUDE.md`

### `docs/claude-advisor-context.md`

- **Added** "Not the same as" block: Claude.ai desktop, Claude mobile, Claude Code / Cursor Claude
- Doctrine: **Advisory proposes** (was Claude proposes)

### `docs/workflow-ownership.md`

- Intro: operator + implementation + advisory surfaces; taxonomy link
- Doctrine: **claude-advisor advises**; **Advisory agents produce memos**; **Operator approves**
- Ownership table: 9 actors (operator, Cursor/Claude Code, Cursor mobile, claude-advisor, Claude.ai, advisory agents, MCP, admins, deterministic repo)
- Tool table: +Cursor mobile, +operator runtime, split Claude into claude-advisor vs Claude.ai
- Handoff protocol: Coordinator → **Operator**; Claude → **claude-advisor**
- MCP: operator-scoped (was coordinator-scoped)
- Forbidden paths list expanded with all surfaces

### `docs/kidweel_agents_as_tools_agility_c1.md`

- **human approval** → **operator approval**
- **Added** boundary note: advisory agents/claude-advisor memos only; Cursor mobile / Claude mobile not runtime boundary

---

## Out of scope (unchanged)

- `src/`, `scripts/`, `tests/`, runtime behavior
- Command syntax (`uv run`, `orb_morning_loop.py`, `operator_status.py`, etc.)
- Gate, approval, or transport wiring

---

## Export commands (host)

```bash
# Patch file
git fetch origin cursor/taxonomy-normalization-7791
git diff main..origin/cursor/taxonomy-normalization-7791 > taxonomy-normalization.patch

# Taxonomy table only
sed -n '/## Surface taxonomy/,/^---$/p' CLAUDE.md

# Full changed-file list
git diff main..origin/cursor/taxonomy-normalization-7791 --name-only
```

---

## Mobile review path

1. Open this file on Cursor mobile or GitHub (`docs/audit/taxonomy_normalization_bundle.md`).
2. For live taxonomy after merge, use `CLAUDE.md` → **Surface taxonomy (authority matters)**.
3. For code diff, open PR #6 **Files changed** tab.
