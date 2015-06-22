# encoding: utf-8
"""
parse_flow.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section

from exabgp.configuration.current.flow.parser import source
from exabgp.configuration.current.flow.parser import destination
from exabgp.configuration.current.flow.parser import any_port
from exabgp.configuration.current.flow.parser import source_port
from exabgp.configuration.current.flow.parser import destination_port
from exabgp.configuration.current.flow.parser import tcp_flags
from exabgp.configuration.current.flow.parser import protocol
from exabgp.configuration.current.flow.parser import next_header
from exabgp.configuration.current.flow.parser import fragment
from exabgp.configuration.current.flow.parser import packet_length
from exabgp.configuration.current.flow.parser import icmp_code
from exabgp.configuration.current.flow.parser import icmp_type
from exabgp.configuration.current.flow.parser import dscp
from exabgp.configuration.current.flow.parser import traffic_class
from exabgp.configuration.current.flow.parser import flow_label


class ParseFlowMatch (Section):
	syntax = \
		'syntax:\n' \
		'  match {\n' \
		'    source 10.0.0.0/24;\n' \
		'    source ::1/128/0;\n' \
		'    destination 10.0.1.0/24;\n' \
		'    port 25;\n' \
		'    source-port >1024\n' \
		'    destination-port =80 =3128 >8080&<8088;\n' \
		'    protocol [ udp tcp ];  (ipv4 only)\n' \
		'    next-header [ udp tcp ]; (ipv6 only)\n' \
		'    fragment [ not-a-fragment dont-fragment is-fragment first-fragment last-fragment ]; (ipv4 only)\n' \
		'    packet-length >200&<300 >400&<500;\n' \
		'    flow-label >100&<2000; (ipv6 only)\n' \
		'}\n'


	known = {
		'source':           source,
		'destination':      destination,
		'port':             any_port,
		'source-port':      source_port,
		'destination-port': destination_port,
		'protocol':         protocol,
		'packet-length':    packet_length,
		'tcp-flags':        tcp_flags,
		'next-header':      next_header,
		'fragment':         fragment,
		'icmp-code':        icmp_code,
		'icmp-type':        icmp_type,
		'packet-length':    packet_length,
		'dscp':             dscp,
		'traffic-class':    traffic_class,
		'flow-label':       flow_label,
	}

	action = {
		'source':           'nlri-add',
		'destination':      'nlri-add',
		'port':             'nlri-add',
		'source-port':      'nlri-add',
		'destination-port': 'nlri-add',
		'protocol':         'nlri-add',
		'packet-length':    'nlri-add',
		'tcp-flags':        'nlri-add',
		'next-header':      'nlri-add',
		'fragment':         'nlri-add',
		'icmp-code':        'nlri-add',
		'icmp-type':        'nlri-add',
		'packet-length':    'nlri-add',
		'dscp':             'nlri-add',
		'traffic-class':    'nlri-add',
		'flow-label':       'nlri-add',
	}

	name = 'flow/match'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def pre (self):
		return True

	def post (self):
		return True
