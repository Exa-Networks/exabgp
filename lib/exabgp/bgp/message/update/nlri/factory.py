# encoding: utf-8
"""
generic.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.nlri.nlri import NLRI

def NLRIFactory (afi,safi,bgp,has_multiple_path,nexthop,action):
	return NLRI.unpack(afi,safi,bgp,has_multiple_path,nexthop,action)
