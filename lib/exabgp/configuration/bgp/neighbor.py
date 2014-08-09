# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised
from exabgp.configuration.engine.section import Section


# ============================================================== syntax_neighbor

syntax_neighbor = """\
neighbor {
	session classical-ibgp
	tcp {
		bind          82.219.212.34
		connect       195.8.215.15"
		ttl-security  disable
		md5           "secret"
	}
	announce {
		local-routes
		off-goes-the-ddos
	}
}
"""

# =============================================================== RaisedNeighbor

class RaisedRaisedNeighbor (Raised):
	syntax = syntax_neighbor


# ============================================================== SectionNeighbor
#

class SectionNeighbor (Section):
	syntax = syntax_neighbor
	name = 'neighbor'
