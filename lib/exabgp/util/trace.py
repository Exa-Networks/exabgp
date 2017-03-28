# encoding: utf-8
"""
trace.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import sys
import traceback

from exabgp.vendoring.six import StringIO


def trace ():
	buff = StringIO.StringIO()
	traceback.print_exc(file=buff)
	r = buff.getvalue()
	buff.close()
	return r
