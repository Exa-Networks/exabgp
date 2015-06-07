#!/usr/bin/env python
# encoding: utf-8
"""
control.py

Created by Thomas Mangin on 2015-01-01.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import time
import socket
import unittest


from exabgp.configuration.setup import environment
environment.setup('')


def speak (name, data):
	time.sleep(0.005)
	try:
		sock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
		sock.connect(name)
		sock.sendall(data)
	except socket.error:
		pass


class TestControl (unittest.TestCase):
	def setUp (self):
		pass

	def test_failed_creation (self):
		pass
		# control = Control()
		# try:
		# 	result = control.init()
		# 	self.assertFalse(result)
		# except IOError:
		# 	# could not write in the location
		# 	pass
		# finally:
		# 	control.cleanup()

	def validate (self, message, check):
		pass
		# name = tempfile.mktemp()
		# control = Control(name,False)
		# try:
		# 	result = control.init()
		# 	self.assertTrue(result)
		#
		# 	p = Process(target=speak, args=(name,message))
		# 	p.start()
		#
		# 	string = control.loop()
		# 	self.assertEqual(string, check)
		# 	p.join()
		# finally:
		# 	control.cleanup()
		# 	del control

	def test_no_newline (self):
		self.validate('x','')

	def test_one_newline (self):
		self.validate('x\n','x')

	def test_two_newline (self):
		self.validate('-\nx\n','x')

	def test_leftover (self):
		self.validate('-\nx\n-','x')

if __name__ == '__main__':
	unittest.main()
