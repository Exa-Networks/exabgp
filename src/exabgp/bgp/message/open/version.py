"""version.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar


class Version(int):
    BGP_4: ClassVar[int] = 4  # RFC 4271 - BGP version 4

    def pack(self) -> bytes:
        return bytes([self])
