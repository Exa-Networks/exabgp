# encoding: utf-8
"""
counter.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2013 Exa Networks. All rights reserved.
"""

import time

# reporting the number of routes we saw
class Counter (object):
	def __init__ (self,logger,me,interval=3):
		self.logger = logger

		self.me = me
		self.interval = interval
		self.last_update = time.time()
		self.count = 0
		self.last_count = 0

	def display (self):
		left = int(self.last_update  + self.interval - time.time())
		if left <=0:
			self.last_update = time.time()
			if self.count > self.last_count:
				self.last_count = self.count
				self.logger.reactor(self.me('processed %d routes' % self.count))

	def increment (self,count):
		self.count += count
