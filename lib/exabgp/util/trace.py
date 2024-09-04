# encoding: utf-8
"""
trace.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import traceback

from exabgp.vendoring.six.moves import StringIO


def trace():
    buff = StringIO()
    traceback.print_exc(file=buff)
    r = buff.getvalue()
    buff.close()
    return r
