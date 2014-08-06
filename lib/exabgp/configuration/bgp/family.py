# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised
from exabgp.configuration.engine.registry import Entry

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI


# ================================================================ family_syntax

family_syntax = \
	'family <name> {\n' \
	'   all  # default, announce all the families we know\n' \
	'\n' \
	'   ipv4 [\n' \
	'      unicast\n' \
	'      multicast\n' \
	'      nlri-mpls\n' \
	'      mpls-vpn\n' \
	'      flow\n' \
	'      flow-vpn\n' \
	'   ]\n' \
	'   ipv6 [\n' \
	'      unicast\n' \
	'      flow\n' \
	'      flow-vpn\n' \
	'   ]\n' \
	'   l2vpn [\n' \
	'      vpls\n' \
	'   ]\n' \
	'}\n'


# ================================================================= RaisedFamily

class RaisedFamily (Raised):
	syntax = family_syntax


# ================================================================ SectionFamily
#

class SectionFamily (Entry):
	syntax = family_syntax
	name = 'family'

	def enter (self,tokeniser):
		self.content = self.create_section(self.name,tokeniser)

	def exit (self,tokeniser):
		# no verification to do
		pass

	def _add (self,tokeniser,afi_name,safi_names):
		self._check_duplicate(tokeniser,RaisedFamily)
		known = self.content.setdefault(AFI(AFI.value(afi_name)),[])

		for safi_name in safi_names:
			if safi_name not in AFI.implemented_safi(afi_name):
				raise RaisedFamily(tokeniser,'the family pair afi/safi %s/%s is unimplemented' % (afi_name,safi_name))

			safi = SAFI(SAFI.value(safi_name))
			if safi in known:
				raise RaisedFamily(tokeniser,'afi/safi pair already defined in this family')
			known.append(safi)

	def ipv4 (self,tokeniser):
		self._add(tokeniser,'ipv4',tokeniser())

	def ipv6 (self,tokeniser):
		self._add(tokeniser,'ipv6',tokeniser())

	def l2vpn (self,tokeniser):
		self._add(tokeniser,'l2vpn',tokeniser())

	def all (self,tokeniser):
		for afi_name in ('ipv4','ipv6','l2vpn'):
			for safi_name in AFI.implemented_safi(afi_name):
				self._add(tokeniser,afi_name,safi_name)


	@classmethod
	def register (cls,registry,location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter')
		registry.register_hook(cls,'exit',location,'exit')

		for afi in ['ipv4','ipv6','l2vpn']:
			registry.register_hook(cls,'action',location+[afi],afi)

		registry.register_hook(cls,'action',location+['all'],'all')
