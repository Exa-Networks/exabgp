
"""
usage.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import sys
import resource


if sys.platform == 'darwin':
    # darwin returns bytes
    DIVISOR = 1024.0 * 1024.0
else:
    # other OS (AFAIK) return a number of pages
    DIVISOR = 1024.0 * 1024.0 / resource.getpagesize()


def usage(label='usage'):
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    return f'{label}: usertime={rusage.ru_utime} systime={rusage.ru_stime} mem={rusage.ru_maxrss / DIVISOR} mb'
