# encoding: utf-8
"""
dictionary.py

Created by Thomas Mangin on 2015-01-17.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from collections import defaultdict


# ===================================================================== dictdict
# an Hardcoded defaultdict with dict as method

class Dictionary (defaultdict):
	def __init__ (self):
		self.default_factory = dict
