"""direction.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# =================================================================== Direction
#

from __future__ import annotations

from enum import Enum


class Direction(Enum):
    IN = 1
    OUT = 2
