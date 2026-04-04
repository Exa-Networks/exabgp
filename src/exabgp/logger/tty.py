from __future__ import annotations

import sys


def _istty(std):
    try:
        return std.isatty()
    except Exception:
        return False


_std = {
    'stderr': sys.stderr,
    'stdout': sys.stdout,
    'out': sys.stdout,
}


def istty(std):
    return _istty(_std[std])
