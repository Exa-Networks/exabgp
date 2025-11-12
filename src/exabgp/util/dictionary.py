
"""dictionary.py

Created by Thomas Mangin on 2015-01-17.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Any, Callable, Optional


# ===================================================================== dictdict
# an Hardcoded defaultdict with dict as method


class Dictionary(defaultdict):
    default_factory: Optional[Callable[[], Dict[Any, Any]]]

    def __init__(self) -> None:
        self.default_factory = dict
