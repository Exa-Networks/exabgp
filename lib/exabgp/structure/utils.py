# encoding: utf-8
"""
utils.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

#import sys
#import time

import StringIO
import traceback

def hexa (value):
	return "%s" % [(hex(ord(_))) for _ in value]

def dump (value):
	def spaced (value):
		even = None
		for v in value:
			if even is False:
				yield ' '
			yield '%02X' % ord(v)
			even = not even
	return ''.join(spaced(value))

def hexdump (value):
	print hexa(value)

def trace ():
	buff = StringIO.StringIO()
	traceback.print_exc(file=buff)
	r = buff.getvalue()
	buff.close()
	return r
