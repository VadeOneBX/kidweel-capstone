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

Use the README **Trinity** framing: deterministic decision system, paper-only execution guardrails, portable evidence narrative. Avoid “autonomous alpha,” “AI trading brain,” or “production live execution.”

Related: [README.md](../README.md), [system-identity.md](./system-identity.md), [c13-governance.md](./c13-governance.md).
