"""dictionary.py

Created by Thomas Mangin on 2015-01-17.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from exabgp.util.mypyc import mypyc_attr


# ===================================================================== dictdict
# an Hardcoded defaultdict with dict as method


# A native (mypyc compiled) subclass of defaultdict crashes the interpreter on the first
# missing key: its default_factory is never seen by the C defaultdict. Kept a Python class.
@mypyc_attr(native_class=False)
class Dictionary(defaultdict[Any, dict[Any, Any]]):
    def __init__(self) -> None:
        super().__init__(dict)
