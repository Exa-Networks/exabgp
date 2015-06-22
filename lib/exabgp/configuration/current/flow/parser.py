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
from exabgp.bgp.message.update.nlri import Flow

from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute.community.extended import TrafficRate
from exabgp.bgp.message.update.attribute.community.extended import TrafficAction
from exabgp.bgp.message.update.attribute.community.extended import TrafficRedirect
from exabgp.bgp.message.update.attribute.community.extended import TrafficMark
from exabgp.bgp.message.update.attribute.community.extended import TrafficNextHop

from exabgp.rib.change import Change

from exabgp.logger import Logger


def flow (tokeniser):
	return Change(
		Flow(),
		Attributes()
	)

def source (tokeniser):
	data = tokeniser()
	if data.count('/') == 1:
		ip,netmask = data.split('/')
		raw = ''.join(chr(int(_)) for _ in ip.split('.'))
		yield Flow4Source(raw,int(netmask))
		return
	yield Flow6Source(IP.pton(ip),int(netmask),int(offset))


def destination (tokeniser):
	data = tokeniser()
	if data.count('/') == 1:
		ip,netmask = data.split('/')
		raw = ''.join(chr(int(_)) for _ in ip.split('.'))
		yield Flow4Destination(raw,int(netmask))
		return

	ip,netmask,offset = data.split('/')
	yield Flow6Destination(IP.pton(ip),int(netmask),int(offset))


# Expressions


def _operator (string):
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
		raise ValueError('Invalid expression (too short) %s' % string)


def _value (self, string):
	l = 0
	for c in string:
		if c not in ['&',]:
			l += 1
			continue
		break
	return string[:l],string[l:]


# parse =80 or >80 or <25 or &>10<20
def _generic_expression (tokeniser, klass):
	data = tokensiser()
	for test in data:
		AND = BinaryOperator.NOP
		while test:
			operator,_ = self._operator(test)
			value,test = self._value(_)
			# XXX: should do a check that the rule is valid for the family
			yield klass(AND | operator,klass.converter(value))
			if test:
				if test[0] == '&':
					AND = BinaryOperator.AND
					test = test[1:]
					if not test:
						raise ValueError("Can not finish an expresion on an &")
				else:
					raise ValueError("Unknown binary operator %s" % test[0])


# parse [ content1 content2 content3 ]
def _generic_list (tokeniser, klass):
	name = tokeniser()
	AND = BinaryOperator.NOP
	if name == '[':
		while True:
			name = tokeniser()
			if name == ']':
				break
			yield klass(NumericOperator.EQ | AND,klass.converter(name))
			return

	if name[0] == '=':
		name = name[1:]
	yield klass(NumericOperator.EQ | AND,klass.converter(name))


def _generic_condition (tokeniser, klass):
	if tokens[0][0] in ['=','>','<']:
		for _ in self._generic_expression(tokeniser,klass):
			yield
	for _ in self._generic_list(tokeniser,klass):
		yield _


def any_port (tokeniser):
	for _ in self._generic_condition(tokeniser,FlowAnyPort):
		yield _


def source_port (tokeniser):
	for _ in self._generic_condition(tokeniser,FlowSourcePort):
		yield _


def destination_port (tokeniser):
	for _ in self._generic_condition(tokeniser,FlowDestinationPort):
		yield _


def packet_length (tokeniser):
	for _ in self._generic_condition(tokeniser,FlowPacketLength):
		yield _


def tcp_flags (tokeniser):
	for _ in self._generic_list(tokeniser,FlowTCPFlag):
		yield _


def protocol (tokeniser):
	for _ in self._generic_list(tokeniser,FlowIPProtocol):
		yield _


def next_header (tokeniser):
	for _ in self._generic_list(tokeniser,FlowNextHeader):
		yield _


def icmp_type (tokeniser):
	for _ in self._generic_list(tokeniser,FlowICMPType):
		yield _


def icmp_code (tokeniser):
	for _ in self._generic_list(tokeniser,FlowICMPCode):
		yield _


def fragment (tokeniser):
	for _ in self._generic_list(tokeniser,FlowFragment):
		yield _


def dscp (tokeniser):
	for _ in self._generic_condition(tokeniser,FlowDSCP):
		yield _


def traffic_class (tokeniser):
	for _ in self._generic_condition(tokeniser,FlowTrafficClass):
		yield _


def flow_label (tokeniser):
	for _ in self._generic_condition(tokeniser,FlowFlowLabel):
		yield _


def next_hop (tokeniser):
	return IP.create(tokens.pop(0))


def accept (tokeniser):
	return


def discard (tokeniser):
	# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
	return TrafficRate(ASN(0),0)


def rate_limit (tokeniser):
	# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
	speed = int(tokeniser())
	if speed < 9600 and speed != 0:
		Logger().configuration("rate-limiting flow under 9600 bytes per seconds may not work",'warning')
	if speed > 1000000000000:
		speed = 1000000000000
		Logger().configuration("rate-limiting changed for 1 000 000 000 000 bytes from %s" % tokens[0],'warning')
	return TrafficRate(ASN(0),speed)


def redirect (tokeniser):
	tokens = tokeniser()
	if data[0].count(':') == 1:
		prefix,suffix = data[0].split(':',1)
		if prefix.count('.'):
			raise ValueError('this format has been deprecaded as it does not make sense and it is not supported by other vendors')

		asn = int(prefix)
		route_target = int(suffix)
		if asn >= pow(2,16):
			raise ValueError('asn is a 32 bits number, it can only be 16 bit %s' % route_target)
		if route_target >= pow(2,32):
			raise ValueError('route target is a 32 bits number, value too large %s' % route_target)
		return TrafficRedirect(asn,route_target)

	return IP.create(data.tokeniser()),TrafficNextHop(False)


def redirect_next_hop (tokeniser):
	return TrafficNextHop(False)


def copy (tokeniser):
	return IP.create(tokeniser()),TrafficNextHop(True)


def mark (tokeniser):
	dscp = tokeniser()

	if not dscp.isdigit():
		raise ValueError('dscp is not a number')

	if dscp < 0 or dscp > 0b111111:
		raise ValueError('dscp is not a valid number')

	return TrafficMark(dscp)


def action (tokeniser):
	action = tokeniser()

	sample = 'sample' in action
	terminal = 'terminal' in action

	if not sample and not terminal:
		raise ValueError('invalid flow action')

	return TrafficAction(sample,terminal)
