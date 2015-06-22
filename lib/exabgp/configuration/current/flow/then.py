# encoding: utf-8
"""
parse_flow.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section

from exabgp.configuration.current.flow.parser import accept
from exabgp.configuration.current.flow.parser import discard
from exabgp.configuration.current.flow.parser import rate_limit
from exabgp.configuration.current.flow.parser import redirect
from exabgp.configuration.current.flow.parser import redirect_next_hop
from exabgp.configuration.current.flow.parser import copy
from exabgp.configuration.current.flow.parser import mark
from exabgp.configuration.current.flow.parser import action


class ParseFlowThen (Section):
	syntax = \
		'syntax:\n' \
		'  then {\n' \
		'    accept;\n' \
		'    discard;\n' \
		'    rate-limit 9600;\n' \
		'    redirect 30740:12345;\n' \
		'    redirect 1.2.3.4:5678;\n' \
		'    redirect 1.2.3.4;\n' \
		'    redirect-next-hop;\n' \
		'    copy 1.2.3.4;\n' \
		'    mark 123;\n' \
		'    action sample|terminal|sample-terminal;\n' \
		'  }\n'

	known = {
		'accept':            accept,
		'discard':           discard,
		'rate-limit':        rate_limit,
		'redirect':          redirect,
		'redirect-next-hop': redirect_next_hop,
		'copy':              copy,
		'mark':              mark,
		'action':            action,
	}

	action = {
		'accept':            'nop',
		'discard':           'attribute-add',
		'rate-limit':        'attribute-add',
		'redirect':          'nexthop-and-attribute',
		'redirect-next-hop': 'attribute-add',
		'copy':              'nexthop-and-attribute',
		'mark':              'attribute-add',
		'action':            'attribute-add',
	}

	name = 'flow/match'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def pre (self):
		return True

	def post (self):
		return True
