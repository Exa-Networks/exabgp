"""sequence.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar


class Sequence(int):
    _instance: ClassVar[dict[str, int]] = dict()

    def __new__(cls):
        cls._instance['next'] = cls._instance.get('next', 0) + 1
        return cls._instance['next']
