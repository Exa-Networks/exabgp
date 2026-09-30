"""errstr.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import errno


def errstr(exc: BaseException) -> str:
    # args[0] is the errno of an OSError, and anything at all (often a message) otherwise.
    code: object = exc.args[0] if exc.args else getattr(exc, 'errno', None)
    if not isinstance(code, int):
        return f'[Errno unknown] {exc!s}'
    return f'[Errno {errno.errorcode.get(code, str(code))}] {exc!s}'
