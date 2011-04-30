#!/usr/bin/env python
# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2011-2011 Exa Networks. All rights reserved.
"""

import os
import sys

debug = os.environ.get('DEBUG_EXIT',None)

if debug is None:
	def intercept (type, value, trace):
		import traceback
		print >> sys.stderr, 'the program failed :', value
	sys.excepthook = intercept
elif debug not in ['0','']:
	def intercept (type, value, trace):
		import traceback
		import pdb
		traceback.print_exception(type,value,trace)
		print
		pdb.pm()
	sys.excepthook = intercept

del sys.argv[0]

if sys.argv:
	__file__ = os.path.abspath(sys.argv[0])
	__name__ = '__main__'
	execfile(sys.argv[0])
