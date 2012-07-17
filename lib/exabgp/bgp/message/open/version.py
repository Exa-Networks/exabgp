#!/usr/bin/env python
# encoding: utf-8
"""
version.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

# =================================================================== Version

class Version (int):
	def pack (self):
		return chr(self)
