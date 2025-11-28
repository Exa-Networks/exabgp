from __future__ import annotations

from typing import Generator, Tuple, Type, TypeVar, Union, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from exabgp.configuration.core.parser import Tokeniser

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.update.attribute import Attributes, NextHop, NextHopSelf
from exabgp.bgp.message.update.attribute.community.extended import (
    ExtendedCommunities,
    ExtendedCommunitiesIPv6,
    InterfaceSet,
    TrafficAction,
    TrafficMark,
    TrafficNextHopIPv4IETF,
    TrafficNextHopIPv6IETF,
    TrafficNextHopSimpson,
    TrafficRate,
    TrafficRedirect,
    TrafficRedirectASN4,
    TrafficRedirectIPv6,
)
from exabgp.bgp.message.update.nlri import (
    Flow,
)
from exabgp.bgp.message.update.nlri.flow import (
    BinaryOperator,
    Flow4Destination,
    Flow4Source,
    Flow6Destination,
    Flow6Source,
    FlowAnyPort,
    FlowDestinationPort,
    FlowDSCP,
    FlowFlowLabel,
    FlowFragment,
    FlowICMPCode,
    FlowICMPType,
    FlowIPProtocol,
    FlowNextHeader,
    FlowPacketLength,
    FlowSourcePort,
    FlowTCPFlag,
    FlowTrafficClass,
    NumericOperator,
)
from exabgp.logger import log, lazymsg
from exabgp.protocol.family import (
    AFI,
)
from exabgp.protocol.ip import IP, IPv4, IPv6
from exabgp.rib.change import Change

# TypeVar for flow condition classes
FlowConditionT = TypeVar(
    'FlowConditionT',
    FlowIPProtocol,
    FlowNextHeader,
    FlowAnyPort,
    FlowSourcePort,
    FlowDestinationPort,
    FlowICMPType,
    FlowICMPCode,
    FlowTCPFlag,
    FlowPacketLength,
    FlowDSCP,
    FlowTrafficClass,
    FlowFragment,
    FlowFlowLabel,
)

SINGLE_SLASH = 1  # Format with single slash (IP/prefix)
DOUBLE_SLASH = 2  # IPv6 format with offset (IP/prefix/offset)

# Bit width constants for validation
ASN16_MAX_BITS = 16  # 16-bit ASN field size
ASN32_MAX_BITS = 32  # 32-bit ASN field size
LOCAL_ADMIN_16_BITS = 16  # 16-bit local administrator field
LOCAL_ADMIN_32_BITS = 32  # 32-bit local administrator field
GROUP_ID_BITS = 14  # 14-bit group ID field

# Interface set direction values
DIRECTION_INPUT = 1
DIRECTION_OUTPUT = 2
DIRECTION_INPUT_OUTPUT = 3

# Colon count for interface set format validation
INTERFACE_SET_COLON_COUNT = 3  # Format: transitive:direction:asn:route_target

# Traffic rate limiting constants
MIN_RATE_LIMIT_BPS = 9600  # Minimum rate limit in bytes per second
MAX_RATE_LIMIT_BPS = 1000000000000  # Maximum rate limit (1 terabyte/s)

# DSCP (Differentiated Services Code Point) value range
DSCP_MAX_VALUE = 0b111111  # DSCP is a 6-bit field (0-63)


def flow(tokeniser: 'Tokeniser') -> Change:
    return Change(Flow(), Attributes())


def source(tokeniser: 'Tokeniser') -> Generator[Union[Flow4Source, Flow6Source], None, None]:
    """Update source to handle both IPv4 and IPv6 flows."""
    data: str = tokeniser()
    # Check if it's IPv4
    if data.count('.') == IPv4.DOT_COUNT and data.count(':') == 0:
        ip: str
        netmask: str
        ip, netmask = data.split('/')
        raw: bytes = b''.join(bytes([int(_)]) for _ in ip.split('.'))
        yield Flow4Source(raw, int(netmask))
    # Check if it's IPv6 without an offset
    elif data.count(':') >= IPv6.COLON_MIN and data.count('/') == SINGLE_SLASH:
        ip, netmask = data.split('/')
        yield Flow6Source(IP.pton(ip), int(netmask), 0)
    # Check if it's IPv6 with an offset
    elif data.count(':') >= IPv6.COLON_MIN and data.count('/') == DOUBLE_SLASH:
        offset: str
        ip, netmask, offset = data.split('/')
        yield Flow6Source(IP.pton(ip), int(netmask), int(offset))


def destination(tokeniser: 'Tokeniser') -> Generator[Union[Flow4Destination, Flow6Destination], None, None]:
    """Update destination to handle both IPv4 and IPv6 flows."""
    data: str = tokeniser()
    # Check if it's IPv4
    if data.count('.') == IPv4.DOT_COUNT and data.count(':') == 0:
        ip: str
        netmask: str
        ip, netmask = data.split('/')
        raw: bytes = b''.join(bytes([int(_)]) for _ in ip.split('.'))
        yield Flow4Destination(raw, int(netmask))
    # Check if it's IPv6 without an offset
    elif data.count(':') >= IPv6.COLON_MIN and data.count('/') == SINGLE_SLASH:
        ip, netmask = data.split('/')
        yield Flow6Destination(IP.pton(ip), int(netmask), 0)
    # Check if it's IPv6 with an offset
    elif data.count(':') >= IPv6.COLON_MIN and data.count('/') == DOUBLE_SLASH:
        offset: str
        ip, netmask, offset = data.split('/')
        yield Flow6Destination(IP.pton(ip), int(netmask), int(offset))


# Expressions


def _operator_numeric(string: str) -> Tuple[int, str]:
    try:
        char: str = string[0].lower()
        if char == '=':
            return NumericOperator.EQ, string[1:]
        operator: int
        if char == '>':
            operator = NumericOperator.GT
        elif char == '<':
            operator = NumericOperator.LT
        elif char == '!':
            if string.startswith('!='):
                return NumericOperator.NEQ, string[2:]
            raise ValueError('invalid operator syntax {}'.format(string))
        elif char == 't' and string.lower().startswith('true'):
            return NumericOperator.TRUE, string[4:]
        elif char == 'f' and string.lower().startswith('false'):
            return NumericOperator.FALSE, string[5:]
        else:
            return NumericOperator.EQ, string
        if string[1] == '=':
            operator += NumericOperator.EQ
            return operator, string[2:]
        return operator, string[1:]
    except IndexError:
        raise ValueError('Invalid expression (too short) {}'.format(string)) from None


def _operator_binary(string: str) -> Tuple[int, str]:
    try:
        if string[0] == '=':
            return BinaryOperator.MATCH, string[1:]
        if string[0] == '!':
            if string.startswith('!='):
                return BinaryOperator.DIFF, string[2:]
            return BinaryOperator.NOT, string[1:]
        return BinaryOperator.INCLUDE, string
    except IndexError:
        raise ValueError('Invalid expression (too short) {}'.format(string)) from None


def _value(string: str) -> Tuple[str, str]:
    ls: int = 0
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
def _generic_condition(tokeniser: 'Tokeniser', klass: Type[FlowConditionT]) -> Generator[FlowConditionT, None, None]:
    _operator = _operator_binary if klass.OPERATION == 'binary' else _operator_numeric
    data: str = tokeniser()
    AND: int = BinaryOperator.NOP
    if data == '[':
        data = tokeniser()
        while True:
            if data == ']':
                break
            operator: int
            _: str
            operator, _ = _operator(data)
            value: str
            value, data = _value(_)
            # XXX: should do a check that the rule is valid for the family
            yield klass(AND | operator, klass.converter(value))
            if data:
                if data[0] != '&':
                    raise ValueError('Unknown binary operator {}'.format(data[0]))
                AND = BinaryOperator.AND
                data = data[1:]
                if not data:
                    raise ValueError('Can not finish an expresion on an &')
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
                    raise ValueError('Unknown binary operator {}'.format(data[0]))
                AND = BinaryOperator.AND
                data = data[1:]


def any_port(tokeniser: 'Tokeniser') -> Generator[FlowAnyPort, None, None]:
    yield from _generic_condition(tokeniser, FlowAnyPort)


def source_port(tokeniser: 'Tokeniser') -> Generator[FlowSourcePort, None, None]:
    yield from _generic_condition(tokeniser, FlowSourcePort)


def destination_port(tokeniser: 'Tokeniser') -> Generator[FlowDestinationPort, None, None]:
    yield from _generic_condition(tokeniser, FlowDestinationPort)


def packet_length(tokeniser: 'Tokeniser') -> Generator[FlowPacketLength, None, None]:
    yield from _generic_condition(tokeniser, FlowPacketLength)


def tcp_flags(tokeniser: 'Tokeniser') -> Generator[FlowTCPFlag, None, None]:
    yield from _generic_condition(tokeniser, FlowTCPFlag)


def protocol(tokeniser: 'Tokeniser') -> Generator[FlowIPProtocol, None, None]:
    yield from _generic_condition(tokeniser, FlowIPProtocol)


def next_header(tokeniser: 'Tokeniser') -> Generator[FlowNextHeader, None, None]:
    yield from _generic_condition(tokeniser, FlowNextHeader)


def icmp_type(tokeniser: 'Tokeniser') -> Generator[FlowICMPType, None, None]:
    yield from _generic_condition(tokeniser, FlowICMPType)


def icmp_code(tokeniser: 'Tokeniser') -> Generator[FlowICMPCode, None, None]:
    yield from _generic_condition(tokeniser, FlowICMPCode)


def fragment(tokeniser: 'Tokeniser') -> Generator[FlowFragment, None, None]:
    yield from _generic_condition(tokeniser, FlowFragment)


def dscp(tokeniser: 'Tokeniser') -> Generator[FlowDSCP, None, None]:
    yield from _generic_condition(tokeniser, FlowDSCP)


def traffic_class(tokeniser: 'Tokeniser') -> Generator[FlowTrafficClass, None, None]:
    yield from _generic_condition(tokeniser, FlowTrafficClass)


def flow_label(tokeniser: 'Tokeniser') -> Generator[FlowFlowLabel, None, None]:
    yield from _generic_condition(tokeniser, FlowFlowLabel)


def next_hop(tokeniser: 'Tokeniser') -> Union[NextHopSelf, NextHop]:
    value: str = tokeniser()

    if value.lower() == 'self':
        return NextHopSelf(AFI.ipv4)
    ip: IP = IP.create(value)
    return NextHop(ip.top(), ip.pack_ip())


def accept(tokeniser: 'Tokeniser') -> None:
    return


def discard(tokeniser: 'Tokeniser') -> ExtendedCommunities:
    # README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
    return ExtendedCommunities().add(TrafficRate(ASN(0), 0))


def rate_limit(tokeniser: 'Tokeniser') -> ExtendedCommunities:
    # README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
    speed: int = int(tokeniser())
    if speed < MIN_RATE_LIMIT_BPS and speed != 0:
        log.warning(
            lazymsg('flow.rate_limit.warning reason=too_low min_bps={min_bps}', min_bps=MIN_RATE_LIMIT_BPS),
            'configuration',
        )
    if speed > MAX_RATE_LIMIT_BPS:
        speed = MAX_RATE_LIMIT_BPS
        log.warning(
            lazymsg(
                'flow.rate_limit.warning reason=too_high max_bps={max_bps} requested={speed}',
                max_bps=MAX_RATE_LIMIT_BPS,
                speed=speed,
            ),
            'configuration',
        )
    return ExtendedCommunities().add(TrafficRate(ASN(0), speed))


def redirect(tokeniser: 'Tokeniser') -> Tuple[IP, ExtendedCommunities]:
    data: str = tokeniser()
    count: int = data.count(':')

    # the redirect is an IPv4 or an IPv6 nexthop
    if count == 0 or (count > 1 and '[' not in data and ']' not in data):
        return IP.create(data), ExtendedCommunities().add(TrafficNextHopSimpson(False))

    # the redirect is an IPv6 nexthop using [] notation
    if data.startswith('[') and data.endswith(']'):
        return IP.create(data[1:-1]), ExtendedCommunities().add(TrafficNextHopSimpson(False))

    # the redirect is an ipv6:NN route-target using []: notation
    if count > 1:
        if ']:' not in data:
            try:
                ip: IP = IP.create(data)
                return ip, ExtendedCommunities().add(TrafficNextHopSimpson(False))
            except (OSError, ValueError):
                raise ValueError('it looks like you tried to use an IPv6 but did not enclose it in []') from None

        nn: str
        ip_str: str
        ip_str, nn = data.split(']:')
        ip_str = ip_str.replace('[', '', 1)

        if int(nn) >= pow(2, LOCAL_ADMIN_16_BITS):
            raise ValueError('Local administrator field is a 16 bits number, value too large {}'.format(nn))
        return IP.create(ip_str), ExtendedCommunities().add(TrafficRedirectIPv6(ip_str, int(nn)))

    # the redirect is an ASN:NN route-target
    if True:  # count == 1:
        prefix: str
        suffix: str
        prefix, suffix = data.split(':', 1)

        if prefix.count('.'):
            raise ValueError(
                'this format has been deprecated as it does not make sense and it is not supported by other vendors',
            )

        asn: int = int(prefix)
        nn_int: int = int(suffix)

        if asn >= pow(2, ASN32_MAX_BITS):
            raise ValueError('asn is a 32 bits number, value too large {}'.format(asn))

        if asn >= pow(2, ASN16_MAX_BITS):
            if nn_int >= pow(2, LOCAL_ADMIN_16_BITS):
                raise ValueError(
                    'asn is a 32 bits number, local administrator field can only be 16 bit {}'.format(nn_int)
                )
            return IP.NoNextHop, ExtendedCommunities().add(TrafficRedirectASN4(ASN4(asn), nn_int))

        if nn_int >= pow(2, LOCAL_ADMIN_32_BITS):
            raise ValueError('Local administrator field is a 32 bits number, value too large {}'.format(nn_int))

        return IP.NoNextHop, ExtendedCommunities().add(TrafficRedirect(ASN(asn), nn_int))

    raise ValueError('redirect format incorrect')


def redirect_next_hop(tokeniser: 'Tokeniser') -> ExtendedCommunities:
    return ExtendedCommunities().add(TrafficNextHopSimpson(False))


def redirect_next_hop_ietf(tokeniser: 'Tokeniser') -> Union[ExtendedCommunities, ExtendedCommunitiesIPv6]:
    ip: IP = IP.create(tokeniser())
    if ip.ipv4():
        return ExtendedCommunities().add(TrafficNextHopIPv4IETF(cast(IPv4, ip), False))
    return ExtendedCommunitiesIPv6().add(TrafficNextHopIPv6IETF(cast(IPv6, ip), False))


def copy(tokeniser: 'Tokeniser') -> Tuple[IP, ExtendedCommunities]:
    return IP.create(tokeniser()), ExtendedCommunities().add(TrafficNextHopSimpson(True))


def mark(tokeniser: 'Tokeniser') -> ExtendedCommunities:
    value: str = tokeniser()

    if not value.isdigit():
        raise ValueError(f"'{value}' is not a valid DSCP mark value\n  Must be a number 0-{DSCP_MAX_VALUE}")

    dscp_value: int = int(value)

    if dscp_value < 0 or dscp_value > DSCP_MAX_VALUE:
        raise ValueError(f'DSCP value {dscp_value} is out of range\n  Must be 0-{DSCP_MAX_VALUE}')

    return ExtendedCommunities().add(TrafficMark(dscp_value))


def action(tokeniser: 'Tokeniser') -> ExtendedCommunities:
    value: str = tokeniser()

    sample: bool = 'sample' in value
    terminal: bool = 'terminal' in value

    if not sample and not terminal:
        raise ValueError(f"'{value}' is not a valid flow action\n  Valid options: sample, terminal, sample-terminal")

    return ExtendedCommunities().add(TrafficAction(sample, terminal))


def _interface_set(data: str) -> InterfaceSet:
    if data.count(':') != INTERFACE_SET_COLON_COUNT:
        raise ValueError(
            f"'{data}' is not a valid interface-set\n"
            f'  Format: <transitive|non-transitive>:<input|output|input-output>:<asn>:<group-id>'
        )

    trans: str
    direction: str
    prefix: str
    suffix: str
    trans, direction, prefix, suffix = data.split(':', INTERFACE_SET_COLON_COUNT)

    trans_bool: bool
    if trans == 'transitive':
        trans_bool = True
    elif trans == 'non-transitive':
        trans_bool = False
    else:
        raise ValueError(f"'{trans}' is not a valid transitivity type\n  Valid options: transitive, non-transitive")
    if prefix.count('.'):
        raise ValueError(f"'{prefix}' is not a valid ASN\n  Must be a 32-bit integer (not dotted notation)")
    int_direction: int
    if direction == 'input':
        int_direction = DIRECTION_INPUT
    elif direction == 'output':
        int_direction = DIRECTION_OUTPUT
    elif direction == 'input-output':
        int_direction = DIRECTION_INPUT_OUTPUT
    else:
        raise ValueError(f"'{direction}' is not a valid direction\n  Valid options: input, output, input-output")
    asn: int = int(prefix)
    route_target: int = int(suffix)
    if asn >= pow(2, ASN32_MAX_BITS):
        raise ValueError(f'ASN {asn} is too large\n  Maximum is {pow(2, ASN32_MAX_BITS) - 1} (32 bits)')
    if route_target >= pow(2, GROUP_ID_BITS):
        raise ValueError(f'group-id {route_target} is too large\n  Maximum is {pow(2, GROUP_ID_BITS) - 1} (14 bits)')
    return InterfaceSet(trans_bool, ASN(asn), route_target, int_direction)


def interface_set(tokeniser: 'Tokeniser') -> ExtendedCommunities:
    communities: ExtendedCommunities = ExtendedCommunities()

    value: str = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == ']':
                break
            communities.add(_interface_set(value))
    else:
        communities.add(_interface_set(value))

    return communities
