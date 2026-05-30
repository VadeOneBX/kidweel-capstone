"""SpotGamma export ingestion for replay corpus staging (no backtest gates)."""

from qops.ingest.spotgamma_loader import (
    discover_processed_weekly_csvs,
    discover_raw_session_dirs,
    discover_spy_history_csvs,
    detect_csv_profile,
    detect_xlsx_profile,
    load_processed_weekly_csv,
    load_scanner_xlsx,
    load_spy_history_csv,
    normalize_header_label,
    parse_numeric,
    parse_trade_date,
)
from qops.ingest.spotgamma_normalize import (
    SpotGammaContextRow,
    build_context_corpus,
    contexts_to_dataframe,
    count_by_source_profile,
    load_raw_profile_contexts,
    missing_field_summary,
    summarize_corpus,
)

__all__ = [
    "SpotGammaContextRow",
    "build_context_corpus",
    "contexts_to_dataframe",
    "count_by_source_profile",
    "detect_csv_profile",
    "detect_xlsx_profile",
    "discover_processed_weekly_csvs",
    "discover_raw_session_dirs",
    "discover_spy_history_csvs",
    "load_processed_weekly_csv",
    "load_raw_profile_contexts",
    "load_scanner_xlsx",
    "load_spy_history_csv",
    "missing_field_summary",
    "normalize_header_label",
    "parse_numeric",
    "parse_trade_date",
    "summarize_corpus",
]
