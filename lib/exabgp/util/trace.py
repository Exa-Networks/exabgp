# encoding: utf-8
"""
trace.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""
import sys

from exabgp.vendoring import six
from six.moves import StringIO

import traceback


def trace ():
	buff = StringIO.StringIO()
	traceback.print_exc(file=buff)
	r = buff.getvalue()
	buff.close()
	return r
