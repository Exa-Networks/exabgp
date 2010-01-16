#!/usr/bin/env python
# encoding: utf-8
"""
interface.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

class IByteStream (object):
	"""The object can be serialised into a byte stream"""
	
	def pack (self):
		raise NotImplementedError('This function must be created by the subclass')


