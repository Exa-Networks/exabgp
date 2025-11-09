
"""
errstr.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import errno


def errstr(exc):
    try:
        code = exc.args[0] if exc.args else exc.errno
        return f'[Errno {errno.errorcode.get(code, str(code))}] {str(exc)}'
    except KeyError:
        return f'[Errno unknown (key)] {str(exc)}'
    except AttributeError:
        return f'[Errno unknown (attr)] {str(exc)}'
