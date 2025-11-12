from __future__ import annotations

import sys
from typing import Any, Dict


def _istty(std: Any) -> bool:
    try:
        return bool(std.isatty())
    except Exception:
        return False


_std: Dict[str, Any] = {
    'stderr': sys.stderr,
    'stdout': sys.stdout,
    'out': sys.stdout,
}


def istty(std: str) -> bool:
    return _istty(_std[std])
