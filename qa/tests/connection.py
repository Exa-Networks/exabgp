#!/usr/bin/env python
# encoding: utf-8
"""
connection.py

Created by Thomas Mangin on 2013-07-13.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import cProfile

import unittest

from exabgp.util.od import od


def test ():
	OPEN = ''.join([chr(int(_,16)) for _ in "FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF 00 1D 01 04 78 14 00 5A 52 DB 00 45 00".split()])
	KEEP = ''.join([chr(int(_,16)) for _ in "FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF 00 00 04".split()])

	from exabgp.reactor.network.outgoing import Outgoing
	connection = Outgoing(1,'82.219.0.69','82.219.212.34')
	writer = connection.writer(OPEN)
	while writer.next() is False:
		pass
	writer = connection.writer(KEEP)
	while writer.next() is False:
		pass

	reader = connection.reader()

	for size,msg,header,body,notification in reader:
		if size:
			print od(header+body)
		else:
			sys.stdout.write('-')

	reader = connection.reader()

	for size,msg,header,body,notification in reader:
		if size:
			print od(header+body)
		else:
			sys.stdout.write('+')

	connection.close()


class TestData (unittest.TestCase):

	def test_1 (self):
		# if not os.environ.get('profile',False):
		# 	result = test()
		# 	if result:
		# 		self.fail(result)
		pass

	def test_2 (self):
		# if not not os.environ.get('profile',False):
		# 	cProfile.run('test()')
		pass

if __name__ == '__main__':
	unittest.main()

	# import cProfile
	# print 'profiling'
	# cProfile.run('unittest.main()','profile.info')
