# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import string
import sys

def string_is_hex (s):
	if s[:2].lower() != '0x':
		return False
	if len(s) <= 2:
		return False
	return all(c in string.hexdigits for c in s[2:])

# for Python3+, let's redefine ord into something
# that plays along nicely with ord(data[42]) with
# data being of type 'bytes'
if sys.version_info[0]<3:
	ord_ = ord
else:
	def ord_(x):
		return x if type(x)==int else ord(x)


if sys.version_info[0]<3:
	chr_ = chr
else:
	def chr_(x):
		return bytes([x])


if sys.version_info[0]<3:
	def padding(n):
		return '\0'*n
else:
	def padding(n):
		return bytes(n)
