# encoding: utf-8
"""
utils.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

#import sys
#import time

import StringIO
import traceback

def hexa (value):
	return "%s" % [(hex(ord(_))) for _ in value]

def hexdump (value):
	print hexa(value)

def trace ():
	buff = StringIO.StringIO()
	traceback.print_exc(file=buff)
	r = buff.getvalue()
	buff.close()
	return r
