# # encoding: utf-8
# """
# neighbor.py

# Created by Thomas Mangin on 2014-06-22.
# Copyright (c) 2014-2014 Exa Networks. All rights reserved.
# """

# from exabgp.configuration.engine.registry import Raised
# from exabgp.configuration.engine.section import Section


# # ============================================================== neighbor_syntax

# neighbor_syntax = \
# 	'family <name>{\n' \
# 	'   all  # default, announce all the families we know\n' \
# 	'\n' \
# 	'   ipv4 {\n' \
# 	'      unicast\n' \
# 	'      multicast\n' \
# 	'      nlri-mpls\n' \
# 	'      mpls-vpn\n' \
# 	'      flow\n' \
# 	'      flow-vpn\n' \
# 	'   }\n' \
# 	'   ipv6 {\n' \
# 	'      unicast\n' \
# 	'      flow\n' \
# 	'      flow-vpn\n' \
# 	'   }\n' \
# 	'   l2vpn {\n' \
# 	'      vpls\n' \
# 	'   }\n' \
# 	'}\n'.replace('\t','   ')

# # =============================================================== RaisedNeighbor

# class RaisedRaisedNeighbor (Raised):
# 	syntax = neighbor_syntax


# # ============================================================== SectionNeighbor
# #

# class SectionNeighbor (Entry):
# 	syntax = neighbor_syntax
# 	name = 'neighbor'
