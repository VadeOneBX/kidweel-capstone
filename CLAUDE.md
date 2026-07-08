# Kidweel — Claude project footing

**Doctrine**

- **Advisory proposes** (claude-advisor, advisory agents). **The system decides.** **Transport executes.**
- **More agents do not mean more authority.**
- **Subagents help the system see; they do not help the system act.**

Agent policy: [AGENTS.md](AGENTS.md). Manifests: [.claude/agents/](.claude/agents/). Skills: [.claude/skills/](.claude/skills/).

---

## Surface taxonomy (authority matters)

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

---

## 1. Project purpose

Kidweel is a **deterministic, paper-only** options decision system: context → playbook → structure → validation → payload → paper transport → audit. It enforces playbook, reward/risk, and PMP constraints before any transport handoff—not by predicting markets.

Constraint Survivability: automation creates leverage; constraints determine whether that leverage survives scale.

See [README.md](README.md) and [docs/system-identity.md](docs/system-identity.md).

---

## 2. Paper-only posture

- **No live trading.**
- **No live endpoint** (`https://api.alpaca.markets` is forbidden for transport).
- Paper transport uses **`ALPACA_PAPER_*`** and **`ALPACA_PAPER_BASE_URL`** exactly `https://paper-api.alpaca.markets`.
- Transport defaults to **dry-run**; real paper submit requires explicit user intent and dedicated paper packets.
- See [docs/alpaca-paper-bridge.md](docs/alpaca-paper-bridge.md).

---

## 3. Canonical authority chain

1. POLICY packets  
2. STRUCTURE packets  
3. Approved implementation packets  
4. Historical canonicals (context only when newer POLICY/STRUCTURE exists)  
5. Legacy research artifacts  

Details: [docs/c13-governance.md](docs/c13-governance.md), [docs/system-identity.md](docs/system-identity.md), [docs/subagent-governance.md](docs/subagent-governance.md), [docs/subagency-proof.md](docs/subagency-proof.md).

---

## 4. Forbidden actions

- **No submit, close, cancel, or replace** unless the user explicitly requests a **dedicated paper packet** with repo gates satisfied.
- **Never print secrets.** **Never `cat .env`** or dump credential files.
- **Never stage `.env`** or **`data/processed`** broker CSVs.
- Do not mutate approval gates, thresholds, PMP policy, spread math, or execution payloads without an approved implementation packet.
- Do not call Alpaca paper transport, MCP order tools, or autonomous broker loops from advisory agents or skills.
- Do not upgrade `structure_bias`; `SKIP` remains `SKIP`.
- Do not re-derive protected fields (`regime_label`, `confidence`, `gamma_ratio`).

---

## 5. Canonical local test commands

From repo root (venv active if used):

```bash
PYTHONPATH=src python -m pytest tests -q
```

Targeted safety-related tests:

```bash
PYTHONPATH=src python -m pytest tests/test_alpaca_paper_bridge.py tests/test_paper_closeout.py -q
```

If tests fail: report the **failing assertion** and **stop**. Do not patch execution paths to “make green” without a packet.

---

## 6. Canonical safety commands

Read-only / audit only (no submit, no `.env` display):

```bash
git status --short
git diff --cached --name-only
grep -R 'pattern' -- path/to/scope
```

Verification when user asks:

```bash
PYTHONPATH=src python -m pytest tests -q
```

Alpaca CLI (only in user-scoped paper packets): use `--quiet`; treat exit code **2** as auth failure; never `--live` or `--secret` on CLI. See [docs/system-identity.md](docs/system-identity.md#alpaca-credential-and-paper-safety).

---

## 7. Packet discipline

- One implementation packet at a time; do not expand scope beyond the packet.
- Treat schemas and playbooks as immutable contracts.
- Docs/agent config packets do not change execution code unless the packet explicitly allows it.
- Only the **coordinator** delegates agents/skills; agents do not spawn agents.
- Apply [OVERARCHING SKILL USE DISCIPLINE-C1](docs/subagent-governance.md#overarching-skill-use-discipline-overarching-skill-use-discipline-c1): before acting, check skill applicability first.

---

## 8. Reference docs

| Doc | Role |
|-----|------|
| [docs/system-identity.md](docs/system-identity.md) | Identity, structure policy, paper safety |
| [docs/c13-governance.md](docs/c13-governance.md) | Authority order |
| [docs/subagent-governance.md](docs/subagent-governance.md) | Subagent spawn, MCP, stop rules |
| [docs/subagency-proof.md](docs/subagency-proof.md) | Skill proof, reference map |
| [docs/claude-advisor-context.md](docs/claude-advisor-context.md) | Advisor role |
| [docs/advisory-group-layer.md](docs/advisory-group-layer.md) | Advisory layering (stub) |
| [docs/advisory-group-matrix.md](docs/advisory-group-matrix.md) | Group matrix (stub) |
| [docs/sg-advisory-model.md](docs/sg-advisory-model.md) | SpotGamma advisory model (stub) |
| [docs/alpaca-paper-bridge.md](docs/alpaca-paper-bridge.md) | Paper transport contract |
| [docs/paper-closeout.md](docs/paper-closeout.md) | Closeout posture |

---

## 9. What to do when blocked

- **Test failure:** Report failing assertion and stop.
- **Scope conflict:** Report conflict and stop.
- **Missing reference doc or packet context:** Report missing context and stop.
- **Credential ambiguity:** Report and stop; do not retry submit.
- **Do not invent fallback behavior** (no synthetic data, no alternate endpoints, no gate workarounds).
