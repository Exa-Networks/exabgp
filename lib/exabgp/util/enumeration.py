# encoding: utf-8
'''
Enumeration.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
'''

class Enumeration (object):
	def __init__(self, *names):
		for number, name in enumerate(names):
			setattr(self, name, pow(2,number))

	def text (self,number):
		for name in dir(self):
			if getattr(self,name) == number:
				return name
