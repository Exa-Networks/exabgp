#!/usr/bin/env python
# encoding: utf-8
"""
connection.py

Created by Thomas Mangin on 2013-07-13.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import sys
import unittest

from exabgp.util.od import od

def test ():
	OPEN = ''.join([chr(int(_,16)) for _ in "FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF 00 1D 01 04 78 14 00 5A 52 DB 00 45 00".split()])
	KEEP = ''.join([chr(int(_,16)) for _ in "FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF 00 00 04".split()])

	from exabgp.reactor.network.outgoing import Outgoing
	connection = Outgoing(1,'82.219.0.5','82.219.212.34')
	writer=connection._writer(OPEN)
	while writer() == False:
		pass
	writer=connection._writer(KEEP)
	while writer() == False:
		pass

	reader=connection.reader()

	for size,kind,header,body in reader:
		if size: print od(header+body)
		else: sys.stdout.write('-')

	reader=connection.reader()

	for size,kind,header,body in reader:
		if size: print od(header+body)
		else: sys.stdout.write('+')

	connection.close()

class TestData (unittest.TestCase):

	def test_1 (self):
		if not os.environ.get('profile',False):
			result = test()
			if result: self.fail(result)

	def test_2 (self):
		if not not os.environ.get('profile',False):
			cProfile.run('test()')

if __name__ == '__main__':
	unittest.main()


	# import cProfile
	# print 'profiling'
	# cProfile.run('unittest.main()','profile.info')
