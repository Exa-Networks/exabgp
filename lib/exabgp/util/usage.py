# encoding: utf-8
"""
usage.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

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
    return '%s: usertime=%s systime=%s mem=%s mb' % (
        label,
        rusage.ru_utime,
        rusage.ru_stime,
        (rusage.ru_maxrss / DIVISOR),
    )
