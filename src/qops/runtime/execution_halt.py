from __future__ import annotations

from pathlib import Path


def assert_not_halted(base_dir: Path) -> None:
    halt_path = base_dir / "data/.execution_halt"
    if halt_path.exists():
        raise RuntimeError("HALTED_BY_OPERATOR")
