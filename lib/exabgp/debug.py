# encoding: utf-8
"""
debug.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""
try:
	import os
	import sys

	def bug_report (type, value, trace):
		import traceback
		from exabgp.logger import Logger
		logger = Logger()

		print
		print
		print "-"*80
		print "-- Please provide the information below on :"
		print "-- https://github.com/Exa-Networks/exabgp/issues"
		print "-"*80
		print
		print
		print '-- Version'
		print
		print
		print sys.version
		print
		print
		print "-- Configuration"
		print
		print
		print logger.config()
		print
		print
		print "-- Logging History"
		print
		print
		print logger.history()
		print
		print
		print "-- Traceback"
		print
		print
		traceback.print_exception(type,value,trace)
		print
		print
		print "-"*80
		print "-- Please provide the information above on :"
		print "-- https://github.com/Exa-Networks/exabgp/issues"
		print "-"*80
		print
		print

		#print >> sys.stderr, 'the program failed with message :', value

	def intercept (type, value, trace):
		bug_report(type, value, trace)
		if os.environ.get('PDB',None) not in [None,'0','']:
			import pdb
			pdb.pm()

	sys.excepthook = intercept

	del sys.argv[0]

	if sys.argv:
		__file__ = os.path.abspath(sys.argv[0])
		__name__ = '__main__'
		execfile(sys.argv[0])
except KeyboardInterrupt:
	sys.exit(1)
