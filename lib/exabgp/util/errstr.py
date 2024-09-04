# encoding: utf-8
"""
errstr.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import errno


def errstr(exc):
    try:
        code = exc.args[0] if exc.args else exc.errno
        return '[Errno %s] %s' % (errno.errorcode.get(code, str(code)), str(exc))
    except KeyError:
        return '[Errno unknown (key)] %s' % str(exc)
    except AttributeError:
        return '[Errno unknown (attr)] %s' % str(exc)
