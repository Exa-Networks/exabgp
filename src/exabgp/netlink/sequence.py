
"""
sequence.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from typing import Dict

class Sequence(int):
    _instance: Dict[str, int] = dict()

    def __new__(cls):
        cls._instance['next'] = cls._instance.get('next', 0) + 1
        return cls._instance['next']
