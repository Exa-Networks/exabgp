"""backlog.py

A byte counting queue of read chunks.

The API and CLI helpers buffer whatever they can not forward yet. They must be
able to tell how many bytes are queued in order to stop a source which sends
faster than the other end consumes, and a plain deque only knows how many chunks
it holds.

Created by Thomas Mangin on 2026-08-20.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections import deque


class Backlog:
    """A FIFO of byte chunks which keeps a running total of its size."""

    __slots__ = ('_chunks', '_nbytes')

    def __init__(self) -> None:
        self._chunks: deque[bytes] = deque()
        self._nbytes: int = 0

    def append(self, chunk: bytes) -> None:
        self._chunks.append(chunk)
        self._nbytes += len(chunk)

    def popleft(self) -> bytes:
        chunk = self._chunks.popleft()
        self._nbytes -= len(chunk)
        return chunk

    def clear(self) -> None:
        self._chunks.clear()
        self._nbytes = 0

    @property
    def nbytes(self) -> int:
        """Total number of bytes queued."""
        return self._nbytes

    def __bool__(self) -> bool:
        return bool(self._chunks)

    def __len__(self) -> int:
        return len(self._chunks)
