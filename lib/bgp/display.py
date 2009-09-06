#!/usr/bin/env python
# encoding: utf-8
"""
display.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import sys
import time

class Display (object):
	follow = True

	def log (self,string):
		if self.follow:
			try:
				print time.strftime('%j %H:%M:%S',time.localtime()), '%15s/%7s' % (self.neighbor.peer_address.human(),self.neighbor.peer_as), string
				sys.stdout.flush()
			except IOError:
				# ^C was pressed while the output is going via a pipe, just ignore the fault, to close the BGP session correctly
				pass
	
	def logIf (self,test,string):
		if test: self.log(string)
