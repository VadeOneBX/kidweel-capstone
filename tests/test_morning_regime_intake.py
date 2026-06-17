"""Morning regime file contracts and ingestion wake (SCHED-C1c)."""

from __future__ import annotations

from pathlib import Path

import pytest

from qops.ingest.file_contracts import evaluate_ingestion_file
from qops.ingest.ingestion_wake import run_ingestion_wake
from qops.runtime.orb_manifest import manifest_path, read_manifest


@pytest.mark.parametrize(
    "name,accepted",
    [
        ("morning_regime_2026-06-16.xlsx", True),
        ("spotgamma_morning_2026-06-16.csv", True),
        ("SG_morning.xlsx", True),
        ("regime_scan.csv", True),
        ("sg_20260616.xlsx", True),
        ("notes.txt", False),
        ("screenshot.png", False),
        ("unknown_file.json", False),
    ],
)
def test_evaluate_ingestion_file(tmp_path: Path, name: str, accepted: bool) -> None:
    path = tmp_path / name
    path.write_text("x", encoding="utf-8")
    result = evaluate_ingestion_file(path, run_date="2026-06-16")
    assert result.accepted is accepted
    if accepted:
        assert result.normalized_name is not None
        assert result.normalized_name.startswith("2026-06-16_")


def test_ingestion_wake_stages_and_rejects(tmp_path: Path) -> None:
    inbox = tmp_path / "data/spotgamma/inbox"
    inbox.mkdir(parents=True)
    (inbox / "morning_regime.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (inbox / "notes.txt").write_text("nope", encoding="utf-8")

    manifest = run_ingestion_wake(tmp_path, mode="manual", dry_run=False)

    assert manifest.files_found == 2
    assert manifest.files_staged == 1
    assert manifest.files_rejected == 1
    assert manifest.status == "FILES_STAGED"
    assert not (inbox / "morning_regime.csv").exists()
    assert not (inbox / "notes.txt").exists()
    staged = list(
        (tmp_path / "data/spotgamma/staging").glob(f"{manifest.run_date}_morning_regime.csv")
    )
    assert len(staged) == 1
    assert manifest_path(tmp_path, manifest.run_date).exists()
    roundtrip = read_manifest(tmp_path, manifest.run_date)
    assert roundtrip.run_id == manifest.run_id


def test_ingestion_wake_no_files_writes_manifest(tmp_path: Path) -> None:
    manifest = run_ingestion_wake(tmp_path, mode="orb-watchdog", dry_run=False)
    assert manifest.status == "NO_FILES"
    assert manifest_path(tmp_path, manifest.run_date).exists()


def test_execution_halt_blocks_paper_submit(tmp_path: Path) -> None:
    from qops.execution.alpaca_paper_bridge import run_paper_payload_transport
    from qops.execution.paper_payload_candidate import PaperPayloadCandidate
    from qops.schemas.playbook import AllowedPlaybook

    halt = tmp_path / "data/.execution_halt"
    halt.parent.mkdir(parents=True)
    halt.write_text("", encoding="utf-8")

    payload = PaperPayloadCandidate(
        payload_id="pay001",
        approval_id="app001",
        symbol="SPY",
        trade_date="2026-06-13",
        structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
        order_class="mleg",
        order_type="limit",
        time_in_force="day",
        qty=1,
        limit_price=1.05,
        max_loss=1.05,
        max_profit=3.95,
        reward_risk=3.76,
        pmp=0.35,
        pmp_source="short_leg_delta_proxy",
        pmp_confidence="LOW",
        expected_value=0.10,
        long_leg_symbol="SPY260620C00420000",
        short_leg_symbol="SPY260620C00425000",
        long_leg_side="buy",
        short_leg_side="sell",
        long_leg_qty=1,
        short_leg_qty=1,
        expiration="2026-06-20",
        approval_status="APPROVED_FOR_PAPER_REVIEW",
        payload_status="PAPER_PAYLOAD_READY",
        payload_reason="paper_payload_fields_valid",
        failure_reasons="",
        provenance="payload_c1_paper_candidate",
    )

    with pytest.raises(RuntimeError, match="HALTED_BY_OPERATOR"):
        run_paper_payload_transport(
            [payload],
            submit_paper=True,
            require_paper_endpoint=False,
            submit_fn=lambda _c, _p, **_: {},
            base_dir=tmp_path,
        )
