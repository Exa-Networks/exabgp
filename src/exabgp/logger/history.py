from __future__ import annotations

from collections import deque

from exabgp.logger.format import _long_color_formater as formater

_history = deque()
_max_history = 20


def history():
    return '\n'.join(formater(*_) for _ in _history)


def record(message, source, level, timestamp):
    if len(_history) > _max_history:
        _history.popleft()
    _history.append((message, source, level, timestamp))
