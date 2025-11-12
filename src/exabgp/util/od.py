
"""od.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Iterator, Optional


def od(value: bytes) -> str:
    def spaced(value: bytes) -> Iterator[str]:
        even: Optional[bool] = None
        for v in value:
            if even is False:
                yield ' '
            yield '{:02X}'.format(v)
            even = not even

    return ''.join(spaced(value))
