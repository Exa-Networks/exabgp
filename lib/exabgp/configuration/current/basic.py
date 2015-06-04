# encoding: utf-8
"""
parse_basic.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute import Attribute


class Split (int):
	ID = Attribute.CODE.INTERNAL_SPLIT


class Watchdog (str):
	ID = Attribute.CODE.INTERNAL_WATCHDOG


class Withdrawn (object):
	ID = Attribute.CODE.INTERNAL_WITHDRAW


class Name (str):
	ID = Attribute.CODE.INTERNAL_NAME


class Basic (object):
	# will raise ValueError if the ASN is not correct
	@staticmethod
	def newASN (value):
		if value.count('.'):
			high,low = value.split('.',1)
			as_number = (int(high) << 16) + int(low)
		else:
			as_number = int(value)
		return ASN(as_number)

	def __init__ (self, error):
		self.error = error

	def clear (self):
		pass

	def boolean (self, scope, command, value, default='true'):
		if not value:
			return self.error.set('invalid %s command (valid options are true or false)' % command)

		boolean = value[0].lower() if value else default

		if boolean in ('true','enable','enabled'):
			scope[-1][command] = True
			return True
		if boolean in ('false','disable','disabled'):
			scope[-1][command] = False
			return True
		if boolean in ('unset',):
			scope[-1][command] = None
			return True

		return self.error.set('invalid %s command (valid options are true or false)' % command)
