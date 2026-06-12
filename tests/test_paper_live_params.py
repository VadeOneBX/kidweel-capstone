from qops.config.paper_live_params import (
    NOTEBOOK_BULL_CALL_REFERENCE,
    NOTEBOOK_SOURCE,
    REPO_PAPER_LIVE_DEFAULTS,
)


def test_notebook_reference_dte_window_is_21_60() -> None:
    assert NOTEBOOK_BULL_CALL_REFERENCE.dte_min == 21
    assert NOTEBOOK_BULL_CALL_REFERENCE.dte_max == 60


def test_repo_paper_live_defaults_not_zero_dte_locked() -> None:
    assert REPO_PAPER_LIVE_DEFAULTS.dte_min == 0
    assert REPO_PAPER_LIVE_DEFAULTS.dte_max == 14


def test_notebook_source_path() -> None:
    assert NOTEBOOK_SOURCE.endswith("options-bull-call-spread.ipynb")
