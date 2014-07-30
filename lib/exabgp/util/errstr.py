# encoding: utf-8
"""
errstr.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import errno

def errstr (e):
	try:
		return '[errno %s], %s' % (errno.errorcode[e.args[0]],str(e))
	except KeyError:
		return '[errno unknown], %s' % str(e)
