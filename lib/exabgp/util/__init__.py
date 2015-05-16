# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import string


def string_is_hex (s):
	if s[:2].lower() != '0x':
		return False
	if len(s) <= 2:
		return False
	return all(c in string.hexdigits for c in s[2:])
