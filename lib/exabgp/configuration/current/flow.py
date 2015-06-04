# encoding: utf-8
"""
parse_route.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop

from exabgp.bgp.message.open.asn import ASN

# from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.flow import BinaryOperator
from exabgp.bgp.message.update.nlri.flow import NumericOperator
from exabgp.bgp.message.update.nlri.flow import Flow4Source
from exabgp.bgp.message.update.nlri.flow import Flow4Destination
from exabgp.bgp.message.update.nlri.flow import Flow6Source
from exabgp.bgp.message.update.nlri.flow import Flow6Destination
from exabgp.bgp.message.update.nlri.flow import FlowSourcePort
from exabgp.bgp.message.update.nlri.flow import FlowDestinationPort
from exabgp.bgp.message.update.nlri.flow import FlowAnyPort
from exabgp.bgp.message.update.nlri.flow import FlowIPProtocol
from exabgp.bgp.message.update.nlri.flow import FlowNextHeader
from exabgp.bgp.message.update.nlri.flow import FlowTCPFlag
from exabgp.bgp.message.update.nlri.flow import FlowFragment
from exabgp.bgp.message.update.nlri.flow import FlowPacketLength
from exabgp.bgp.message.update.nlri.flow import FlowICMPType
from exabgp.bgp.message.update.nlri.flow import FlowICMPCode
from exabgp.bgp.message.update.nlri.flow import FlowDSCP
from exabgp.bgp.message.update.nlri.flow import FlowTrafficClass
from exabgp.bgp.message.update.nlri.flow import FlowFlowLabel

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended import TrafficRate
from exabgp.bgp.message.update.attribute.community.extended import TrafficAction
from exabgp.bgp.message.update.attribute.community.extended import TrafficRedirect
from exabgp.bgp.message.update.attribute.community.extended import TrafficMark
from exabgp.bgp.message.update.attribute.community.extended import TrafficNextHop

from exabgp.configuration.current.basic import Basic


class ParseFlow (Basic):
	syntax = \
		'syntax:\n' \
		'flow {\n' \
		'   route give-me-a-name\n' \
		'      route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535; (optional)\n' \
		'      next-hop 1.2.3.4; (to use with redirect-to-nexthop)\n' \
		'      match {\n' \
		'        source 10.0.0.0/24;\n' \
		'        source ::1/128/0;\n' \
		'        destination 10.0.1.0/24;\n' \
		'        port 25;\n' \
		'        source-port >1024\n' \
		'        destination-port =80 =3128 >8080&<8088;\n' \
		'        protocol [ udp tcp ];  (ipv4 only)\n' \
		'        next-header [ udp tcp ]; (ipv6 only)\n' \
		'        fragment [ not-a-fragment dont-fragment is-fragment first-fragment last-fragment ]; (ipv4 only)\n' \
		'        packet-length >200&<300 >400&<500;\n' \
		'        flow-label >100&<2000; (ipv6 only)\n' \
		'      }\n' \
		'      then {\n' \
		'        accept;\n' \
		'        discard;\n' \
		'        rate-limit 9600;\n' \
		'        redirect 30740:12345;\n' \
		'        redirect 1.2.3.4:5678;\n' \
		'        redirect 1.2.3.4;\n' \
		'        redirect-next-hop;\n' \
		'        copy 1.2.3.4;\n' \
		'        mark 123;\n' \
		'        action sample|terminal|sample-terminal;\n' \
		'      }\n' \
		'   }\n' \
		'}\n\n' \
		'one or more match term, one action\n' \
		'fragment code is totally untested\n'

	def __init__ (self, error, logger):
		self.error = error
		self.logger = logger
		self.state = 'out'

	def clear (self):
		self.state = 'out'

	# Command Flow

	def source (self, scope, tokens):
		try:
			data = tokens.pop(0)
			if data.count('/') == 1:
				ip,netmask = data.split('/')
				raw = ''.join(chr(int(_)) for _ in ip.split('.'))

				if not scope[-1]['announce'][-1].nlri.add(Flow4Source(raw,int(netmask))):
					return self.error.set('Flow can only have one destination')

			else:
				ip,netmask,offset = data.split('/')
				change = scope[-1]['announce'][-1]
				change.nlri.afi = AFI(AFI.ipv6)
				if not change.nlri.add(Flow6Source(IP.pton(ip),int(netmask),int(offset))):
					return self.error.set('Flow can only have one destination')
			return True

		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def destination (self, scope, tokens):
		try:
			data = tokens.pop(0)
			if data.count('/') == 1:
				ip,netmask = data.split('/')
				raw = ''.join(chr(int(_)) for _ in ip.split('.'))

				if not scope[-1]['announce'][-1].nlri.add(Flow4Destination(raw,int(netmask))):
					return self.error.set('Flow can only have one destination')

			else:
				ip,netmask,offset = data.split('/')
				change = scope[-1]['announce'][-1]
				# XXX: This is ugly
				change.nlri.afi = AFI(AFI.ipv6)
				if not change.nlri.add(Flow6Destination(IP.pton(ip),int(netmask),int(offset))):
					return self.error.set('Flow can only have one destination')
			return True

		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	# to parse the port configuration of flow

	def _operator (self, string):
		try:
			if string[0] == '=':
				return NumericOperator.EQ,string[1:]
			elif string[0] == '>':
				operator = NumericOperator.GT
			elif string[0] == '<':
				operator = NumericOperator.LT
			else:
				raise ValueError('Invalid operator in test %s' % string)
			if string[1] == '=':
				operator += NumericOperator.EQ
				return operator,string[2:]
			else:
				return operator,string[1:]
		except IndexError:
			raise Exception('Invalid expression (too short) %s' % string)

	def _value (self, string):
		l = 0
		for c in string:
			if c not in ['&',]:
				l += 1
				continue
			break
		return string[:l],string[l:]

	# parse =80 or >80 or <25 or &>10<20
	def _generic_expression (self, scope, tokens, klass):
		try:
			for test in tokens:
				AND = BinaryOperator.NOP
				while test:
					operator,_ = self._operator(test)
					value,test = self._value(_)
					nlri = scope[-1]['announce'][-1].nlri
					# XXX: should do a check that the rule is valid for the family
					nlri.add(klass(AND | operator,klass.converter(value)))
					if test:
						if test[0] == '&':
							AND = BinaryOperator.AND
							test = test[1:]
							if not test:
								raise ValueError("Can not finish an expresion on an &")
						else:
							raise ValueError("Unknown binary operator %s" % test[0])
			return True
		except ValueError,exc:
			return self.error.set(self.syntax + str(exc))

	# parse [ content1 content2 content3 ]
	def _generic_list (self, scope, tokens, klass):
		try:
			name = tokens.pop(0)
			AND = BinaryOperator.NOP
			if name == '[':
				while True:
					name = tokens.pop(0)
					if name == ']':
						break
					try:
						nlri = scope[-1]['announce'][-1].nlri
						# XXX: should do a check that the rule is valid for the family
						nlri.add(klass(NumericOperator.EQ | AND,klass.converter(name)))
					except IndexError:
						return self.error.set(self.syntax)
			else:
				if name[0] == '=':
					name = name[1:]
				scope[-1]['announce'][-1].nlri.add(klass(NumericOperator.EQ | AND,klass.converter(name)))
		except (IndexError,ValueError):
			return self.error.set(self.syntax)
		return True

	def _generic_condition (self, scope, tokens, klass):
		if tokens[0][0] in ['=','>','<']:
			return self._generic_expression(scope,tokens,klass)
		return self._generic_list(scope,tokens,klass)

	def anyport (self, scope, tokens):
		return self._generic_condition(scope,tokens,FlowAnyPort)

	def source_port (self, scope, tokens):
		return self._generic_condition(scope,tokens,FlowSourcePort)

	def destination_port (self, scope, tokens):
		return self._generic_condition(scope,tokens,FlowDestinationPort)

	def packet_length (self, scope, tokens):
		return self._generic_condition(scope,tokens,FlowPacketLength)

	def tcp_flags (self, scope, tokens):
		return self._generic_list(scope,tokens,FlowTCPFlag)

	def protocol (self, scope, tokens):
		return self._generic_list(scope,tokens,FlowIPProtocol)

	def next_header (self, scope, tokens):
		return self._generic_list(scope,tokens,FlowNextHeader)

	def icmp_type (self, scope, tokens):
		return self._generic_list(scope,tokens,FlowICMPType)

	def icmp_code (self, scope, tokens):
		return self._generic_list(scope,tokens,FlowICMPCode)

	def fragment (self, scope, tokens):
		return self._generic_list(scope,tokens,FlowFragment)

	def dscp (self, scope, tokens):
		return self._generic_condition(scope,tokens,FlowDSCP)

	def traffic_class (self, scope, tokens):
		return self._generic_condition(scope,tokens,FlowTrafficClass)

	def flow_label (self, scope, tokens):
		return self._generic_condition(scope,tokens,FlowFlowLabel)

	def next_hop (self, scope, tokens):
		try:
			change = scope[-1]['announce'][-1]

			if change.nlri.nexthop is not NoNextHop:
				return self.error.set(self.syntax)

			change.nlri.nexthop = IP.create(tokens.pop(0))
			return True

		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def accept (self, scope, tokens):
		return True

	def discard (self, scope, tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			scope[-1]['announce'][-1].attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficRate(ASN(0),0))
			return True
		except ValueError:
			return self.error.set(self.syntax)

	def rate_limit (self, scope, tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			speed = int(tokens[0])
			if speed < 9600 and speed != 0:
				self.logger.configuration("rate-limiting flow under 9600 bytes per seconds may not work",'warning')
			if speed > 1000000000000:
				speed = 1000000000000
				self.logger.configuration("rate-limiting changed for 1 000 000 000 000 bytes from %s" % tokens[0],'warning')
			scope[-1]['announce'][-1].attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficRate(ASN(0),speed))
			return True
		except ValueError:
			return self.error.set(self.syntax)

	def redirect (self, scope, tokens):
		try:
			if tokens[0].count(':') == 1:
				prefix,suffix = tokens[0].split(':',1)
				if prefix.count('.'):
					raise ValueError('this format has been deprecaded as it does not make sense and it is not supported by other vendors')
				else:
					asn = int(prefix)
					route_target = int(suffix)
					if asn >= pow(2,16):
						raise ValueError('asn is a 32 bits number, it can only be 16 bit %s' % route_target)
					if route_target >= pow(2,32):
						raise ValueError('route target is a 32 bits number, value too large %s' % route_target)
					scope[-1]['announce'][-1].attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficRedirect(asn,route_target))
					return True
			else:
				change = scope[-1]['announce'][-1]
				if change.nlri.nexthop is not NoNextHop:
					return self.error.set(self.syntax)

				nh = IP.create(tokens.pop(0))
				change.nlri.nexthop = nh
				change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficNextHop(False))
				return True

		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def redirect_next_hop (self, scope, tokens):
		try:
			change = scope[-1]['announce'][-1]

			if change.nlri.nexthop is NoNextHop:
				return self.error.set(self.syntax)

			change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficNextHop(False))
			return True

		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def copy (self, scope, tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			if scope[-1]['announce'][-1].attributes.has(Attribute.CODE.NEXT_HOP):
				return self.error.set(self.syntax)

			change = scope[-1]['announce'][-1]
			change.nlri.nexthop = IP.create(tokens.pop(0))
			change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficNextHop(True))
			return True

		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def mark (self, scope, tokens):
		try:
			dscp = int(tokens.pop(0))

			if dscp < 0 or dscp > 0b111111:
				return self.error.set(self.syntax)

			change = scope[-1]['announce'][-1]
			change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficMark(dscp))
			return True

		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def action (self, scope, tokens):
		try:
			action = tokens.pop(0)
			sample = 'sample' in action
			terminal = 'terminal' in action

			if not sample and not terminal:
				return self.error.set(self.syntax)

			change = scope[-1]['announce'][-1]
			change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficAction(sample,terminal))
			return True
		except (IndexError,ValueError):
			return self.error.set(self.syntax)
