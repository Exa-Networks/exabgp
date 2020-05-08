from exabgp.util import character
from exabgp.util import concat_bytes_i

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop
from exabgp.protocol.family import AFI

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

from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.attribute import NextHopSelf
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute.community.extended import TrafficRate
from exabgp.bgp.message.update.attribute.community.extended import TrafficAction
from exabgp.bgp.message.update.attribute.community.extended import TrafficRedirect
from exabgp.bgp.message.update.attribute.community.extended import TrafficRedirectASN4
from exabgp.bgp.message.update.attribute.community.extended import TrafficMark
from exabgp.bgp.message.update.attribute.community.extended import TrafficRedirectIPv6
from exabgp.bgp.message.update.attribute.community.extended import TrafficNextHopIPv4IETF
from exabgp.bgp.message.update.attribute.community.extended import TrafficNextHopIPv6IETF
from exabgp.bgp.message.update.attribute.community.extended import TrafficNextHopSimpson

from exabgp.bgp.message.update.attribute.community.extended import InterfaceSet

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunitiesIPv6

from exabgp.rib.change import Change

from exabgp.logger import Logger


def flow(tokeniser):
    return Change(Flow(), Attributes())


def source(tokeniser):
    data = tokeniser()
    if data.count('.') == 3 and data.count(':') == 0:
        ip, netmask = data.split('/')
        raw = concat_bytes_i(character(int(_)) for _ in ip.split('.'))
        yield Flow4Source(raw, int(netmask))
    elif data.count('/') == 1:
        ip, netmask = data.split('/')
        offset = 0
        yield Flow6Source(IP.pton(ip), int(netmask), int(offset))
    else:
        ip, netmask, offset = data.split('/')
        yield Flow6Source(IP.pton(ip), int(netmask), int(offset))


def destination(tokeniser):
    data = tokeniser()
    if data.count('.') == 3 and data.count(':') == 0:
        ip, netmask = data.split('/')
        raw = concat_bytes_i(character(int(_)) for _ in ip.split('.'))
        yield Flow4Destination(raw, int(netmask))
    elif data.count('/') == 1:
        ip, netmask = data.split('/')
        offset = 0
        yield Flow6Destination(IP.pton(ip), int(netmask), int(offset))
    else:
        ip, netmask, offset = data.split('/')
        yield Flow6Destination(IP.pton(ip), int(netmask), int(offset))


# Expressions


def _operator_numeric(string):
    try:
        char = string[0].lower()
        if char == '=':
            return NumericOperator.EQ, string[1:]
        elif char == '>':
            operator = NumericOperator.GT
        elif char == '<':
            operator = NumericOperator.LT
        elif char == '!':
            if string.startswith('!='):
                return NumericOperator.NEQ, string[2:]
            raise ValueError('invalid operator syntax %s' % string)
        elif char == 't' and string.lower().startswith('true'):
            return NumericOperator.TRUE, string[4:]
        elif char == 'f' and string.lower().startswith('false'):
            return NumericOperator.FALSE, string[5:]
        else:
            return NumericOperator.EQ, string
        if string[1] == '=':
            operator += NumericOperator.EQ
            return operator, string[2:]
        else:
            return operator, string[1:]
    except IndexError:
        raise ValueError('Invalid expression (too short) %s' % string)


def _operator_binary(string):
    try:
        if string[0] == '=':
            return BinaryOperator.MATCH, string[1:]
        elif string[0] == '!':
            return BinaryOperator.NOT, string[1:]
        else:
            return BinaryOperator.INCLUDE, string
    except IndexError:
        raise ValueError('Invalid expression (too short) %s' % string)


def _value(string):
    ls = 0
    for c in string:
        if c not in [
            '&',
        ]:
            ls += 1
            continue
        break
    return string[:ls], string[ls:]


# parse [ content1 content2 content3 ]
# parse =80 or >80 or <25 or &>10<20
def _generic_condition(tokeniser, klass):
    _operator = _operator_binary if klass.OPERATION == 'binary' else _operator_numeric
    data = tokeniser()
    AND = BinaryOperator.NOP
    if data == '[':
        data = tokeniser()
        while True:
            if data == ']':
                break
            operator, _ = _operator(data)
            value, data = _value(_)
            # XXX: should do a check that the rule is valid for the family
            yield klass(AND | operator, klass.converter(value))
            if data:
                if data[0] != '&':
                    raise ValueError("Unknown binary operator %s" % data[0])
                AND = BinaryOperator.AND
                data = data[1:]
                if not data:
                    raise ValueError("Can not finish an expresion on an &")
            else:
                AND = BinaryOperator.NOP
                data = tokeniser()
    else:
        while data:
            operator, _ = _operator(data)
            value, data = _value(_)
            yield klass(operator | AND, klass.converter(value))
            if data:
                if data[0] != '&':
                    raise ValueError("Unknown binary operator %s" % data[0])
                AND = BinaryOperator.AND
                data = data[1:]


def any_port(tokeniser):
    for _ in _generic_condition(tokeniser, FlowAnyPort):
        yield _


def source_port(tokeniser):
    for _ in _generic_condition(tokeniser, FlowSourcePort):
        yield _


def destination_port(tokeniser):
    for _ in _generic_condition(tokeniser, FlowDestinationPort):
        yield _


def packet_length(tokeniser):
    for _ in _generic_condition(tokeniser, FlowPacketLength):
        yield _


def tcp_flags(tokeniser):
    for _ in _generic_condition(tokeniser, FlowTCPFlag):
        yield _


def protocol(tokeniser):
    for _ in _generic_condition(tokeniser, FlowIPProtocol):
        yield _


def next_header(tokeniser):
    for _ in _generic_condition(tokeniser, FlowNextHeader):
        yield _


def icmp_type(tokeniser):
    for _ in _generic_condition(tokeniser, FlowICMPType):
        yield _


def icmp_code(tokeniser):
    for _ in _generic_condition(tokeniser, FlowICMPCode):
        yield _


def fragment(tokeniser):
    for _ in _generic_condition(tokeniser, FlowFragment):
        yield _


def dscp(tokeniser):
    for _ in _generic_condition(tokeniser, FlowDSCP):
        yield _


def traffic_class(tokeniser):
    for _ in _generic_condition(tokeniser, FlowTrafficClass):
        yield _


def flow_label(tokeniser):
    for _ in _generic_condition(tokeniser, FlowFlowLabel):
        yield _


def next_hop(tokeniser):
    value = tokeniser()

    if value.lower() == 'self':
        return NextHopSelf(AFI.ipv4)
    else:
        ip = IP.create(value)
        return NextHop(ip.top(), ip.pack())


def accept(tokeniser):
    return


def discard(tokeniser):
    # README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
    return ExtendedCommunities().add(TrafficRate(ASN(0), 0))


def rate_limit(tokeniser):
    # README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
    speed = int(tokeniser())
    if speed < 9600 and speed != 0:
        Logger().warning("rate-limiting flow under 9600 bytes per seconds may not work", 'configuration')
    if speed > 1000000000000:
        speed = 1000000000000
        Logger().warning("rate-limiting changed for 1 000 000 000 000 bytes from %s" % speed, 'configuration')
    return ExtendedCommunities().add(TrafficRate(ASN(0), speed))


def redirect(tokeniser):
    data = tokeniser()
    count = data.count(':')
    if count == 0:
        return IP.create(data), ExtendedCommunities().add(TrafficNextHopSimpson(False))
    if count == 1:
        prefix, suffix = data.split(':', 1)
        if prefix.count('.'):
            raise ValueError(
                'this format has been deprecated as it does not make sense and it is not supported by other vendors'
            )

        asn = int(prefix)
        route_target = int(suffix)

        if asn >= pow(2, 32):
            raise ValueError('asn is a 32 bits number, value too large %s' % asn)
        if asn >= pow(2, 16):
            if route_target >= pow(2, 16):
                raise ValueError('asn is a 32 bits number, route target can only be 16 bit %s' % route_target)
            return NoNextHop, ExtendedCommunities().add(TrafficRedirectASN4(asn, route_target))
        if route_target >= pow(2, 32):
            raise ValueError('route target is a 32 bits number, value too large %s' % route_target)
        return NoNextHop, ExtendedCommunities().add(TrafficRedirect(asn, route_target))
    else:
        elements = data.split(':')
        ip = ':'.join(elements[:-1])
        asn = int(elements[-1])
        return IP.create(ip), ExtendedCommunities().add(TrafficRedirectIPv6(ip, asn))


def redirect_next_hop(tokeniser):
    return ExtendedCommunities().add(TrafficNextHopSimpson(False))


def redirect_next_hop_ietf(tokeniser):
    ip = IP.create(tokeniser())
    if ip.ipv4():
        return ExtendedCommunities().add(TrafficNextHopIPv4IETF(ip, False))
    else:
        return ExtendedCommunitiesIPv6().add(TrafficNextHopIPv6IETF(ip, False))


def copy(tokeniser):
    return IP.create(tokeniser()), ExtendedCommunities().add(TrafficNextHopSimpson(True))


def mark(tokeniser):
    value = tokeniser()

    if not value.isdigit():
        raise ValueError('dscp is not a number')

    dscp_value = int(value)

    if dscp_value < 0 or dscp_value > 0b111111:
        raise ValueError('dscp is not a valid number')

    return ExtendedCommunities().add(TrafficMark(dscp_value))


def action(tokeniser):
    value = tokeniser()

    sample = 'sample' in value
    terminal = 'terminal' in value

    if not sample and not terminal:
        raise ValueError('invalid flow action')

    return ExtendedCommunities().add(TrafficAction(sample, terminal))


def _interface_set(data):
    if data.count(':') != 3:
        raise ValueError('not a valid format %s' % data)

    trans, direction, prefix, suffix = data.split(':', 3)

    if trans == 'transitive':
        trans = True
    elif trans == 'non-transitive':
        trans = False
    else:
        raise ValueError('Bad transitivity type %s, should be transitive or non-transitive' % trans)
    if prefix.count('.'):
        raise ValueError('a 32 bits number must be used, invalid value %s' % prefix)
    if direction == 'input':
        int_direction = 1
    elif direction == 'output':
        int_direction = 2
    elif direction == 'input-output':
        int_direction = 3
    else:
        raise ValueError('Bad direction %s, should be input, output or input-output' % direction)
    asn = int(prefix)
    route_target = int(suffix)
    if asn >= pow(2, 32):
        raise ValueError('asn can only be 32 bits, value too large %s' % asn)
    if route_target >= pow(2, 14):
        raise ValueError('group-id is a 14 bits number, value too large %s' % route_target)
    return InterfaceSet(trans, asn, route_target, int_direction)


def interface_set(tokeniser):
    communities = ExtendedCommunities()

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == ']':
                break
            communities.add(_interface_set(value))
    else:
        communities.add(_interface_set(value))

    return communities
