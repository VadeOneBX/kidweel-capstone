"""Morning regime workbook: standard name + upgraded sheet structure."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

from qops.ingest.morning_regime_upgrade import (
    discover_workbook_sheets,
    extract_fast_advisory_candidates,
    is_upgraded_morning_regime_workbook,
    is_upgrade_morning_regime_workbook,
    load_morning_regime_upgrade,
    parse_flow_candidates,
    parse_flow_premium,
    parse_stat_sig_greek_cell,
    parse_stat_sig_positions,
    parse_unusual_options_positions,
    run_morning_regime_intake,
    run_morning_regime_upgrade_intake,
)

_PRIMARY_FIXTURE = Path(__file__).resolve().parent / "data" / "morning_regime.xlsx"
_LEGACY_FIXTURE = Path(__file__).resolve().parent / "data" / "morning_regime_UPGRADE.xlsx"


@pytest.fixture(scope="module")
def morning_regime_workbook() -> Path:
    if _PRIMARY_FIXTURE.is_file():
        return _PRIMARY_FIXTURE
    if _LEGACY_FIXTURE.is_file():
        return _LEGACY_FIXTURE
    pytest.skip("missing fixture: tests/data/morning_regime.xlsx")


def _mara_candidate(workbook: Path):
    intake = load_morning_regime_upgrade(workbook)
    mara = [c for c in intake.fast_advisory_candidates if c.symbol == "MARA"]
    assert len(mara) == 1
    return mara[0]


def test_morning_regime_xlsx_discovers_upgraded_tabs(morning_regime_workbook: Path) -> None:
    sheets = discover_workbook_sheets(morning_regime_workbook)
    assert "morning_regime" in sheets
    assert "unusual_options_positions" in sheets
    assert "stat_sig_positions" in sheets
    assert "flow_candidates" in sheets
    assert is_upgraded_morning_regime_workbook(morning_regime_workbook)
    assert morning_regime_workbook.name in {"morning_regime.xlsx", "morning_regime_UPGRADE.xlsx"}


def test_morning_regime_xlsx_detects_mara_call_spread(morning_regime_workbook: Path) -> None:
    candidate = _mara_candidate(morning_regime_workbook)
    assert candidate.candidate_detected is True
    assert candidate.expiration == "2026-07-02"
    assert candidate.structure_family == "call_spread"
    assert candidate.strikes == (14.5, 15.5)
    assert candidate.spread_id == "Call Spread"
    assert candidate.supporting_unusual_flow is True
    assert candidate.fast_advisory_status in {"WATCH", "REVIEW"}
    assert candidate.paper_submission_status == "gated_not_submitted"
    assert candidate.long_leg_strike == 15.5
    assert candidate.short_leg_strike == 14.5


def test_upgrade_suffix_remains_backward_compatible(
    morning_regime_workbook: Path,
    tmp_path: Path,
) -> None:
    if not _LEGACY_FIXTURE.is_file():
        pytest.skip("legacy UPGRADE fixture not retained")
    assert is_upgraded_morning_regime_workbook(_LEGACY_FIXTURE)
    assert is_upgrade_morning_regime_workbook(_LEGACY_FIXTURE)

    alias_path = tmp_path / "morning_regime.xlsx"
    alias_path.write_bytes(_LEGACY_FIXTURE.read_bytes())
    assert is_upgraded_morning_regime_workbook(alias_path)
    candidate = _mara_candidate(alias_path)
    assert candidate.symbol == "MARA"

    _, audit_path = run_morning_regime_upgrade_intake(tmp_path, alias_path)
    assert audit_path == tmp_path / "logs" / "morning_regime_latest.json"
    assert (tmp_path / "logs" / "morning_regime_upgrade_latest.json").is_file()


def test_images_remain_non_authoritative(morning_regime_workbook: Path, tmp_path: Path) -> None:
    import json

    ocr_modules = [name for name in sys.modules if "ocr" in name.lower()]
    with mock.patch.dict(sys.modules, {m: mock.MagicMock() for m in ocr_modules}):
        intake, audit_path = run_morning_regime_intake(tmp_path, morning_regime_workbook)
    assert intake.image_ocr_used is False
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["image_ocr_used"] is False
    assert audit.get("workbook_format") == "upgraded"


def test_parse_unusual_options_positions(morning_regime_workbook: Path) -> None:
    assert parse_flow_premium("2.11M") == 2_110_000.0
    assert parse_flow_premium("783,872") == 783_872.0
    assert parse_flow_premium("-81.91M") == pytest.approx(-81_910_000.0)

    rows = parse_unusual_options_positions(morning_regime_workbook)
    assert len(rows) == 25
    mara = [r for r in rows if r.symbol == "MARA"]
    assert sorted(r.strike for r in mara) == [14.5, 15.5]


def test_parse_stat_sig_positions_percentiles(morning_regime_workbook: Path) -> None:
    mm, pct, _ = parse_stat_sig_greek_cell("$1433.8, 100th")
    assert mm == pytest.approx(1433.8)
    assert pct == 100
    rows = parse_stat_sig_positions(morning_regime_workbook)
    assert len(rows) == 6


def test_missing_optional_sheets_degrades_gracefully(tmp_path: Path) -> None:
    path = tmp_path / "morning_regime.xlsx"
    narrative = pd.DataFrame({"note": ["Macro Theme:", "Risk-on"]})
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        narrative.to_excel(writer, sheet_name="morning_regime", index=False, header=False)

    intake = load_morning_regime_upgrade(path)
    assert intake.fast_advisory_candidates == ()
    assert is_upgraded_morning_regime_workbook(path) is False


def test_flow_candidate_pairing_without_workbook() -> None:
    from qops.ingest.morning_regime_upgrade import FlowCandidateRow, UnusualOptionsRow

    flow = [
        FlowCandidateRow("MARA", "2026-07-02", 14.5, "C", "Call Spread", source_workbook="t.xlsx"),
        FlowCandidateRow("MARA", "2026-07-02", 15.5, "C", "Call Spread", source_workbook="t.xlsx"),
    ]
    unusual = [
        UnusualOptionsRow(
            symbol="MARA",
            expiration="2026-07-02",
            strike=14.5,
            option_type="C",
            total_volume=1.0,
            bto=None,
            btc=None,
            sto=100.0,
            stc=None,
            buy_premium=None,
            sell_premium=None,
            total_premium=None,
            spread_id="Call Spread Open",
            source_sheet="unusual_options_positions",
            source_workbook="t.xlsx",
        ),
    ]
    candidates = extract_fast_advisory_candidates(flow, unusual, source_workbook="t.xlsx")
    assert len(candidates) == 1


def test_run_intake_writes_neutral_audit(morning_regime_workbook: Path, tmp_path: Path) -> None:
    _, audit_path = run_morning_regime_intake(tmp_path, morning_regime_workbook)
    assert audit_path.name == "morning_regime_latest.json"
    assert len(parse_flow_candidates(morning_regime_workbook)) == 6
