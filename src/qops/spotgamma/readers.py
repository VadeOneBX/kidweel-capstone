"""Load SpotGamma XLSX tables into pandas DataFrames."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_xlsx_table(path: str | Path, *, header: int = 1) -> pd.DataFrame:
    """Read the first worksheet of an XLSX file into a DataFrame.

    SpotGamma portal exports place section headers on the first row and column
    labels on the second row; ``header=1`` is the default.

    Args:
        path: Filesystem path to the workbook.
        header: Row index to use as column names (0-based), per :func:`pandas.read_excel`.

    Returns:
        DataFrame of the first sheet.

    Raises:
        FileNotFoundError: If ``path`` does not exist or is not a file.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"XLSX path does not exist or is not a file: {p.resolve()}")
    return pd.read_excel(p, engine="openpyxl", header=header)
