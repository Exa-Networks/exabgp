# encoding: utf-8
"""
errstr.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import errno

def errstr (e):
	try:
		code = e.args[0] if e.args else e.errno
		return '[Errno %s] %s' % (errno.errorcode.get(code,str(code)),str(e))
	except KeyError:
		return '[Errno unknown (key)] %s' % str(e)
	except AttributeError:
		return '[Errno unknown (attr)] %s' % str(e)
