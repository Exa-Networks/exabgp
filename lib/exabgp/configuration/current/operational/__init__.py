# encoding: utf-8
"""
parse_operational.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section

from exabgp.configuration.current.operational.parser import asm
from exabgp.configuration.current.operational.parser import adm
from exabgp.configuration.current.operational.parser import rpcq
from exabgp.configuration.current.operational.parser import rpcp
from exabgp.configuration.current.operational.parser import apcq
from exabgp.configuration.current.operational.parser import apcp
from exabgp.configuration.current.operational.parser import lpcq
from exabgp.configuration.current.operational.parser import lpcp

class ParseOperational (Section):
	syntax = \
		'syntax:\n' \
		''

	known = {
		'asm':  asm,
		'adm':  adm,
		'rpcq': rpcq,
		'rpcp': rpcp,
		'apcq': apcq,
		'apcp': apcp,
		'lpcq': lpcq,
		'lpcp': lpcp,
	}

	action = {
		'asm':  'set',
		'adm':  'set',
		'rpcq': 'set',
		'rpcp': 'set',
		'apcq': 'set',
		'apcp': 'set',
		'lpcq': 'set',
		'lpcp': 'set',
	}

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		pass

	def pre (self):
		pass

	def post (self):
		pass
