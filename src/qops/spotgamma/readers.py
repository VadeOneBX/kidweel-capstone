"""Load SpotGamma XLSX tables into pandas DataFrames."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_xlsx_table(path: str | Path) -> pd.DataFrame:
    """Read the first worksheet of an XLSX file into a DataFrame.

    Args:
        path: Filesystem path to the workbook.

    Returns:
        DataFrame of the first sheet.

    Raises:
        FileNotFoundError: If ``path`` does not exist or is not a file.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"XLSX path does not exist or is not a file: {p.resolve()}")
    return pd.read_excel(p, engine="openpyxl")
