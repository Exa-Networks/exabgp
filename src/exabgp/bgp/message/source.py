"""change.py

Created by Thomas Mangin on 2022-10-28.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar


class Source:
    UNSET: ClassVar[int] = 0x00
    CONFIGURATION: ClassVar[int] = 0x01
    API: ClassVar[int] = 0x02
    NETWORK: ClassVar[int] = 0x04
