# encoding: utf-8
"""
generic.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.nlri.bgp import BGPNLRI

from exabgp.bgp.message.notification import Notify

def NLRIFactory (afi,safi,data,path_info,nexthop,action):
	if safi in (133,134):
		raise Notify(3,2,'unimplemented')
	else:
		nlri = BGPNLRI(afi,safi,data,path_info,nexthop,action)

	return nlri
