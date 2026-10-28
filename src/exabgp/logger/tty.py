from __future__ import annotations

import sys
from typing import Any


def _istty(std: Any) -> bool:
    try:
        return bool(std.isatty())
    # no isatty, or a stream already closed
    except (AttributeError, OSError, ValueError):
        return False


_std: dict[str, Any] = {
    'stderr': sys.stderr,
    'stdout': sys.stdout,
    'out': sys.stdout,
}


def istty(std: str) -> bool:
    return _istty(_std.get(std, None))
