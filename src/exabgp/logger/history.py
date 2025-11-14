from __future__ import annotations

import time
from collections import deque
from typing import Deque, Tuple

from exabgp.logger.format import _long_color_formater as formater

_history: Deque[Tuple[str, str, str, float]] = deque()
_max_history: int = 20


def history() -> str:
    return '\n'.join(formater(msg, src, lvl, time.localtime(ts)) for msg, src, lvl, ts in _history)


def record(message: str, source: str, level: str, timestamp: float) -> None:
    if len(_history) > _max_history:
        _history.popleft()
    _history.append((message, source, level, timestamp))
