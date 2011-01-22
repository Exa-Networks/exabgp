#!/usr/bin/env python
# encoding: utf-8
"""
utils.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import sys
import time

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

#class Log (object):
#	follow = True
#
#	def __init__ (self,peer,asn):
#		self.peer = peer
#		self.asn = asn
#
#	def out (self,string):
#		if self.follow:
#			try:
#				for line in string.split('\n'):
#					return time.strftime('%j %H:%M:%S',time.localtime()), '%15s/%7s' % (self.peer,self.asn), line
#			except IOError:
#				# ^C was pressed while the output is going via a pipe, just ignore the fault, to close the BGP session correctly
#				pass
#
#	def outIf (self,test,string):
#		if test: 
#			return self.out(string)
#		return ''