# Public readiness and license posture (GOV-C1)

Kidweel is shared for **portfolio review**, capstone demonstration, and technical interview context. It is **not** offered as open-source trading software or a live-trading product.

---

## License posture

- **No MIT license** and no default permissive OSS license in this repository.
- **Default notice:** all rights reserved unless a file or future packet explicitly states otherwise.
- Root [NOTICE](../NOTICE) summarizes viewer rights: read and review for evaluation; no implied license to run as a commercial service, redistribute forks, or strip attribution without permission.

A final legal license (e.g. custom source-available terms) may replace or amend this notice in a dedicated governance packet. Until then, treat the repo as **proprietary capstone work** with public read access where the host platform allows.

---

## What public readers should expect

| Topic | Posture |
|-------|---------|
| Trading | **Paper-only**; dry-run default; no live Alpaca production endpoint |
| Automation | Deterministic gates and explicit operator opt-in for paper submit |
| AI / agents | Proposal and review layers only; no approval or transport authority |
| Evidence | Local `data/` artifacts and audit CSVs; mock docs labeled `synthetic_mock` |
| Secrets | Never commit `.env`; [claude_code_access_runbook.md](./claude_code_access_runbook.md) privacy grep before external share |

---

## Suggested external narrative

Lead with human decision-making inside bounded delegation: **Agents assist. Humans decide. The process records why.**

Use the README **Subagency Proof** bridge and [kidweel-site splash](../kidweel-site/index.html). Emphasize human-in-the-loop review, operator judgment, and audit trails—not autonomous routing, inherited authority, or live-money execution.

Related: [README.md](../README.md), [system-identity.md](./system-identity.md), [c13-governance.md](./c13-governance.md).
