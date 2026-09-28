"""flow.py

The values of a FlowSpec route (RFC 8955, RFC 8956): what it matches and what it does.

Each type reads what the legacy function of configuration/flow/parser.py read, and builds
the same rules and communities. A condition checks its component against the address
family the read has in its context, as the legacy tokeniser's `afi` did: that family is
the one of the last prefix read, a static route's included.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable, cast

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.asn4 import ASN4
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
    TrafficRatePackets,
    TrafficRedirect,
    TrafficRedirectASN4,
    TrafficRedirectIPv6,
)
from exabgp.bgp.message.update.nlri.flow import (
    BinaryOperator,
    Flow4Destination,
    Flow4Source,
    Flow6Destination,
    Flow6Source,
    FlowIPv4,
    FlowIPv6,
    NumericOperator,
)
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.types.base import Printed, Type
from exabgp.configuration.grammar.words import Words
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP, IPSelf, IPv4, IPv6

IPV4_MAX_NETMASK = 32
IPV6_MAX_NETMASK = 128
LOCAL_ADMIN_16 = pow(2, 16)
LOCAL_ADMIN_32 = pow(2, 32)
RATE_LIMIT_BPS_MIN = 9600  # below this a rate limit is warned about
RATE_LIMIT_BPS_MAX = 1000000000000  # above this a rate limit is capped
DSCP_MAX = 0b111111
MAX_CONDITIONS = 1024  # a bracketed list of conditions is written by hand
DIRECTIONS = {'input': 1, 'output': 2, 'input-output': 3}


# `redirect <ip>` and `copy <ip>` changed which community they send, and nothing in the syntax
# tells the old meaning from the new: said once per process, not once per route
_TOLD_ABOUT_THE_IETF_DEFAULT = [False]


def _tell_about_the_ietf_default(keyword: str, older: str) -> None:
    if _TOLD_ABOUT_THE_IETF_DEFAULT[0]:
        return
    _TOLD_ABOUT_THE_IETF_DEFAULT[0] = True
    log.warning(
        lazymsg(
            'flow.redirect.ietf_default keyword={keyword} older={older} '
            'reason=draft-ietf-idr-flowspec-redirect-ip replaces draft-simpson-idr-flowspec-redirect-ip; '
            'the target is now in an extended community and no longer in the MP_REACH_NLRI next hop, '
            'as RFC 8955 section 4 requires. Write "{older}" to keep the previous encoding.',
            keyword=keyword,
            older=older,
        ),
        'configuration',
    )


class Operation(Type[list[Any]]):
    """A value type whose value is built by a function over the words: the flow values.

    `read(words)` returns the value or raises ValueError; the type positions the error.
    """

    def __init__(
        self, name: str, read: Callable[[Words], Any], hint: str, examples: list[str], value: Shape = shape.TEXT
    ) -> None:
        self.name = name
        self._shape = value
        self._read = read
        self._hint = hint
        self._examples = examples

    def parse(self, words: Words) -> Any:
        where = words.where()
        try:
            return self._read(words)
        except ConfigError:
            raise  # positioned already, by the value which failed
        except (ValueError, IndexError, KeyError, TypeError, OSError) as exc:
            raise ConfigError(where, str(exc) or f'invalid {self.name}', expected=[self._hint]) from None

    def render(self, value: Any) -> list[str]:
        # a flow value is printed from the text of its NLRI or community, already as words
        if isinstance(value, Printed):
            return list(value)
        raise ValueError(f'a {self.name} is printed from the route it is in')

    def hint(self) -> str:
        return self._hint

    def examples(self) -> list[str]:
        return list(self._examples)

    def shape(self) -> Shape:
        return self._shape


# --------------------------------------------------------------------------- prefixes


def _prefix(kind: str, klass4: Any, klass6: Any) -> Callable[[Words], list[Any]]:
    def read(words: Words) -> list[Any]:
        data = words.word()
        is_ipv4 = data.count('.') == IPv4.DOT_COUNT and data.count(':') == 0
        is_ipv6 = data.count(':') >= IPv6.COLON_MIN and data.count('/') == 1
        is_ipv6_offset = data.count(':') >= IPv6.COLON_MIN and data.count('/') == 2
        if not (is_ipv4 or is_ipv6 or is_ipv6_offset):
            raise ValueError(f'unrecognised flow {kind} "{data}"')
        try:
            if is_ipv4:
                ip, netmask = data.split('/')
                raw = bytes(int(part) for part in ip.split('.'))
                return [klass4.make_prefix4(raw, _netmask(netmask, IPV4_MAX_NETMASK))]
            if is_ipv6:
                ip, netmask = data.split('/')
                return [klass6.make_prefix6(IP.pton(ip), _netmask(netmask, IPV6_MAX_NETMASK), 0)]
            ip, netmask, offset = data.split('/')
            mask = _netmask(netmask, IPV6_MAX_NETMASK)
            return [klass6.make_prefix6(IP.pton(ip), mask, _offset(offset, mask))]
        except (OSError, IndexError, ValueError) as exc:
            raise ValueError(f'invalid flow {kind} "{data}": {exc}') from None

    return read


def _netmask(netmask: str, maximum: int) -> int:
    mask = int(netmask)
    if not 0 <= mask <= maximum:
        raise ValueError(f'netmask {mask} is not in the range 0-{maximum}')
    return mask


def _offset(offset: str, netmask: int) -> int:
    value = int(offset)
    if not (value == 0 if netmask == 0 else 0 <= value < netmask):
        raise ValueError(f'offset {value} must be zero for /0 or in the range 0-{netmask - 1}')
    return value


# a prefix, and for IPv6 the offset of the bits compared (RFC 8956)
FLOW_PREFIX = shape.string(pattern=rf'{shape.IP_PREFIX.pattern}(/\d{{1,3}})?')
# numeric and bitmask conditions: an operator and a value, joined by & (RFC 8955 4.2.1)
FLOW_CONDITIONS = shape.leaf_list(shape.string(pattern=r'[=<>!]*[0-9a-z-]+(&[=<>!]*[0-9a-z-]+)*'), min_items=1)

SOURCE = Operation(
    'source',
    _prefix('source', Flow4Source, Flow6Source),
    '<ip>/<mask>[/<offset>]',
    ['10.0.0.0/24', '2001:db8::/32'],
    FLOW_PREFIX,
)
DESTINATION = Operation(
    'destination',
    _prefix('destination', Flow4Destination, Flow6Destination),
    '<ip>/<mask>[/<offset>]',
    ['10.0.0.0/24', '2001:db8::/32/8'],
    FLOW_PREFIX,
)

# --------------------------------------------------------------------------- conditions


def _operator_numeric(text: str) -> tuple[int, str]:
    if not text:
        raise ValueError(f'Invalid expression (too short) {text}')
    char = text[0].lower()
    if char == '=':
        return NumericOperator.EQ, text[1:]
    if char == '!':
        if text.startswith('!='):
            return NumericOperator.NEQ, text[2:]
        raise ValueError(f'invalid operator syntax {text}')
    if char == 't' and text.lower().startswith('true'):
        return NumericOperator.TRUE, text[4:]
    if char == 'f' and text.lower().startswith('false'):
        return NumericOperator.FALSE, text[5:]
    if char not in '><':
        return NumericOperator.EQ, text
    operator = NumericOperator.GT if char == '>' else NumericOperator.LT
    if len(text) < 2:
        raise ValueError(f'Invalid expression (too short) {text}')
    if text[1] == '=':
        return operator + NumericOperator.EQ, text[2:]
    return operator, text[1:]


def _operator_binary(text: str) -> tuple[int, str]:
    if not text:
        raise ValueError(f'Invalid expression (too short) {text}')
    if text[0] == '=':
        return BinaryOperator.MATCH, text[1:]
    if text[0] == '!':
        if text.startswith('!='):
            return BinaryOperator.DIFF, text[2:]
        return BinaryOperator.NOT, text[1:]
    return BinaryOperator.INCLUDE, text


def _split_value(text: str) -> tuple[str, str]:
    """The value up to the first `&`, and what follows."""
    index = text.find('&')
    return (text, '') if index < 0 else (text[:index], text[index:])


def _condition(klass: Any) -> Callable[[Words], list[Any]]:
    """`<op><value>[&<op><value>...]`, or several in brackets, of one component type."""

    def read(words: Words) -> list[Any]:
        afi = words.context.afi
        if afi == AFI.ipv4 and not issubclass(klass, FlowIPv4):
            raise ValueError(f"'{klass.__name__}' is not valid for IPv4 flow routes (IPv6-only component)")
        if afi == AFI.ipv6 and not issubclass(klass, FlowIPv6):
            raise ValueError(f"'{klass.__name__}' is not valid for IPv6 flow routes (IPv4-only component)")
        operator = _operator_binary if klass.OPERATION == 'binary' else _operator_numeric
        data = words.word()
        if data == '[':
            return _bracketed(words, klass, operator)
        return _expression(data, klass, operator, BinaryOperator.NOP)[0]

    return read


def _expression(data: str, klass: Any, operator: Any, joined: int, bracketed: bool = False) -> tuple[list[Any], int]:
    """The rules of one word, `>80&<90`: each joined to the one before it by AND after the first.

    legacy: a word ending on `&` is refused in brackets and taken outside them.
    """
    rules: list[Any] = []
    for _ in range(MAX_CONDITIONS):
        if not data:
            return rules, BinaryOperator.NOP
        code, rest = operator(data)
        value, data = _split_value(rest)
        rules.append(klass(code | joined, klass.converter(value)))
        if data:
            joined = BinaryOperator.AND
            data = data[1:]
            if not data and bracketed:
                raise ValueError('Can not finish an expresion on an &')
    raise ValueError(f'a flow expression holds at most {MAX_CONDITIONS} values')


def _bracketed(words: Words, klass: Any, operator: Any) -> list[Any]:
    rules: list[Any] = []
    for _ in range(MAX_CONDITIONS):
        data = words.word()
        if data == ']':
            return rules
        found, _joined = _expression(data, klass, operator, BinaryOperator.NOP, bracketed=True)
        rules.extend(found)
    raise ValueError(f'a flow condition list holds at most {MAX_CONDITIONS} values')


def condition(name: str, klass: Any, examples: list[str]) -> Operation:
    return Operation(name, _condition(klass), '<op><value>[&...] | [ ... ]', examples, FLOW_CONDITIONS)


# --------------------------------------------------------------------------- actions


def _discard(words: Words) -> ExtendedCommunities:
    # the AS is zero, as Juniper and Arbor made it for a local flow route
    return ExtendedCommunities().add(TrafficRate.make_traffic_rate(ASN(0), 0))


def _rate_limit(words: Words) -> ExtendedCommunities:
    speed = int(words.word())
    unit = 'bytes'
    if words.peek() in ('bytes', 'packets'):
        unit = words.word()
    if unit == 'packets':
        return ExtendedCommunities().add(TrafficRatePackets.make_traffic_rate_packets(ASN(0), speed))
    if speed < RATE_LIMIT_BPS_MIN and speed != 0:
        log.warning(
            lazymsg('flow.rate_limit.warning reason=too_low min_bps={m}', m=RATE_LIMIT_BPS_MIN), 'configuration'
        )
    if speed > RATE_LIMIT_BPS_MAX:
        speed = RATE_LIMIT_BPS_MAX
        log.warning(
            lazymsg('flow.rate_limit.warning reason=too_high max_bps={m}', m=RATE_LIMIT_BPS_MAX), 'configuration'
        )
    return ExtendedCommunities().add(TrafficRate.make_traffic_rate(ASN(0), speed))


def _redirect_target(words: Words) -> str:
    """The target as one word: the lexer splits `[2001:db8::1]:100` at the brackets."""
    data = words.word()
    if data != '[':
        return data
    address = words.word()
    if words.word() != ']':
        raise ValueError(f'redirect [{address} is missing its closing bracket')
    if words.peek().startswith(':'):
        return f'[{address}]{words.word()}'
    return f'[{address}]'


def _nexthop_ietf(ip: IP, copy: bool) -> ExtendedCommunities | ExtendedCommunitiesIPv6:
    if ip.ipv4():
        return ExtendedCommunities().add(TrafficNextHopIPv4IETF.make_traffic_nexthop_ipv4(cast(IPv4, ip), copy))
    return ExtendedCommunitiesIPv6().add(TrafficNextHopIPv6IETF.make_traffic_nexthop_ipv6(cast(IPv6, ip), copy))


def _redirect_ipv6(data: str) -> tuple[IP, ExtendedCommunitiesIPv6]:
    address, number = data[1:].split(']:', 1)
    if IP.from_string(address).ipv4():
        raise ValueError(f'redirect {data} needs an IPv6 address, an IPv4 one is written without []')
    if not number.isdigit():
        raise ValueError(f'redirect {data} needs a number after the address')
    if int(number) >= LOCAL_ADMIN_16:
        raise ValueError(f'Local administrator field is a 16 bits number, value too large {number}')
    return IP.NoNextHop, ExtendedCommunitiesIPv6().add(
        TrafficRedirectIPv6.make_traffic_redirect_ipv6(address, int(number))
    )


def _redirect(words: Words) -> tuple[IP, Any]:
    data = _redirect_target(words)
    if data.startswith('[') and ']:' in data:
        return _redirect_ipv6(data)
    count = data.count(':')
    if count == 0 or (count > 1 and '[' not in data and ']' not in data):
        _tell_about_the_ietf_default('redirect <ip>', 'redirect-simpson <ip>')
        return IP.NoNextHop, _nexthop_ietf(IP.from_string(data), False)
    if data.startswith('[') and data.endswith(']'):
        _tell_about_the_ietf_default('redirect <ip>', 'redirect-simpson <ip>')
        return IP.NoNextHop, _nexthop_ietf(IP.from_string(data[1:-1]), False)
    if count > 1:
        try:
            ip = IP.from_string(data)
        except (OSError, ValueError):
            raise ValueError('it looks like you tried to use an IPv6 but did not enclose it in []') from None
        _tell_about_the_ietf_default('redirect <ip>', 'redirect-simpson <ip>')
        return IP.NoNextHop, _nexthop_ietf(ip, False)
    return IP.NoNextHop, _redirect_asn(data)


def _redirect_asn(word: str) -> ExtendedCommunities:
    """`<asn>:<nn>`, a redirect to a VRF by route-target."""
    prefix, suffix = word.split(':', 1)
    if prefix.count('.'):
        raise ValueError(
            'this format has been deprecated as it does not make sense and it is not supported by other vendors'
        )
    asn, number = int(prefix), int(suffix)
    if not ASN4.validate(asn):
        raise ValueError(f'asn is invalid, must be 0 to {ASN.MAX_4BYTE} (32 bits): {asn}')
    if asn > ASN.MAX_2BYTE:
        if number >= LOCAL_ADMIN_16:
            raise ValueError(f'asn is a 32 bits number, local administrator field can only be 16 bit {number}')
        return ExtendedCommunities().add(TrafficRedirectASN4.make_traffic_redirect_asn4(ASN4(asn), number))
    if number >= LOCAL_ADMIN_32:
        raise ValueError(f'Local administrator field is a 32 bits number, value too large {number}')
    return ExtendedCommunities().add(TrafficRedirect.make_traffic_redirect(ASN(asn), number))


def _simpson(copy: bool) -> ExtendedCommunities:
    return ExtendedCommunities().add(TrafficNextHopSimpson.make_traffic_nexthop_simpson(copy))


def _redirect_to_nexthop(words: Words) -> Any:
    # with no address the older Simpson form, with one the IETF form
    if not words.peek():
        return _simpson(False)
    return _nexthop_ietf(IP.from_string(words.word()), False)


def _redirect_simpson(words: Words) -> tuple[IP, ExtendedCommunities]:
    data = _redirect_target(words)
    if data.startswith('[') and data.endswith(']'):
        data = data[1:-1]
    try:
        ip = IP.from_string(data)
    except (OSError, ValueError):
        # a route-target passes nothing in the next-hop: the operator is told why, not inet_pton's complaint
        raise ValueError(
            f'redirect-simpson takes an address and {data} is not one. A redirect to a route-target puts '
            f'nothing in the next hop and is conformant already, so it has no -simpson form: write "redirect {data}".'
        ) from None
    return ip, _simpson(False)


def _mark(words: Words) -> ExtendedCommunities:
    value = words.word()
    if not value.isdigit() or int(value) > DSCP_MAX:
        raise ValueError(f"'{value}' is not a valid DSCP mark value, it is 0-{DSCP_MAX}")
    return ExtendedCommunities().add(TrafficMark.make_traffic_mark(int(value)))


def _action(words: Words) -> ExtendedCommunities:
    value = words.word()
    sample, terminal = 'sample' in value, 'terminal' in value
    if not sample and not terminal:
        raise ValueError(f"'{value}' is not a valid flow action, it is sample, terminal or sample-terminal")
    return ExtendedCommunities().add(TrafficAction.make_traffic_action(sample, terminal))


def _one_interface_set(word: str) -> InterfaceSet:
    parts = word.split(':')
    if len(parts) == 4:
        transitive, direction, asn, group = parts
        if transitive not in ('transitive', 'non-transitive'):
            raise ValueError(f"'{transitive}' is not a valid transitivity type")
    elif len(parts) == 3:
        transitive, (direction, asn, group) = 'transitive', parts
    else:
        raise ValueError(f"'{word}' is not a valid interface-set")
    if asn.count('.'):
        raise ValueError(f"'{asn}' is not a valid ASN, it is a 32-bit integer")
    if direction not in DIRECTIONS:
        raise ValueError(f"'{direction}' is not a valid direction, it is input, output or input-output")
    number, group_id = int(asn), int(group)
    if not ASN4.validate(number):
        raise ValueError(f'ASN {number} is invalid, it is 0 to {ASN.MAX_4BYTE}')
    if not InterfaceSet.validate_group_id(group_id):
        raise ValueError(f'group-id {group_id} is invalid, it is 0 to {InterfaceSet.GROUP_ID_MAX}')
    return InterfaceSet.make_interface_set(ASN(number), group_id, DIRECTIONS[direction], transitive == 'transitive')


def _interface_set(words: Words) -> ExtendedCommunities:
    communities = ExtendedCommunities()
    value = words.word()
    if value != '[':
        return communities.add(_one_interface_set(value))
    for _ in range(MAX_CONDITIONS):
        value = words.word()
        if value == ']':
            return communities
        communities.add(_one_interface_set(value))
    raise ValueError(f'an interface-set list holds at most {MAX_CONDITIONS} values')


def _flow_nexthop(words: Words) -> IP:
    value = words.word()
    if value.lower() == 'self':
        return IPSelf(AFI.ipv4)
    return IP.from_string(value)


def _nothing(words: Words) -> None:
    return None


ACCEPT = Operation('accept', _nothing, '', [''], shape.empty())
DISCARD = Operation('discard', _discard, '', [''], shape.empty())
RATE_LIMIT = Operation(
    'rate-limit',
    _rate_limit,
    '<number> [bytes|packets]',
    ['0', '9600', '100 packets'],
    shape.container(
        ('rate', shape.integer(0, RATE_LIMIT_BPS_MAX).described('a larger rate in bytes is capped')),
        ('unit', shape.enumeration('bytes', 'packets').described('what the rate counts, bytes by default')),
    ),
)
REDIRECT = Operation(
    'redirect',
    _redirect,
    '<asn>:<nn>|<ip>|[<ipv6>]:<nn>',
    ['65000:1', '10.0.0.1'],
    shape.union(shape.string(pattern=r'\d+:\d+|\[[0-9a-fA-F:.]+\]:\d+'), shape.IP_ADDRESS),
)
REDIRECT_TO_NEXTHOP = Operation(
    'redirect-to-nexthop',
    _redirect_to_nexthop,
    '[<ip>]',
    ['', '10.0.0.1'],
    shape.union(shape.empty(), shape.IP_ADDRESS),
)
REDIRECT_TO_NEXTHOP_IETF = Operation(
    'redirect-to-nexthop-ietf',
    lambda words: _nexthop_ietf(IP.from_string(words.word()), False),
    '<ip>',
    ['10.0.0.1'],
    shape.IP_ADDRESS,
)
REDIRECT_TO_NEXTHOP_SIMPSON = Operation(
    'redirect-to-nexthop-simpson', lambda words: _simpson(False), '', [''], shape.empty()
)
REDIRECT_SIMPSON = Operation('redirect-simpson', _redirect_simpson, '<ip>', ['10.0.0.1'], shape.IP_ADDRESS)


def _copy(words: Words) -> tuple[IP, Any]:
    _tell_about_the_ietf_default('copy <ip>', 'copy-simpson <ip>')
    return IP.NoNextHop, _nexthop_ietf(IP.from_string(words.word()), True)


COPY = Operation('copy', _copy, '<ip>', ['10.0.0.1'], shape.IP_ADDRESS)
COPY_SIMPSON = Operation(
    'copy-simpson', lambda words: (IP.from_string(words.word()), _simpson(True)), '<ip>', ['10.0.0.1'], shape.IP_ADDRESS
)
MARK = Operation('mark', _mark, '<0-63>', ['0', '63'], shape.integer(0, DSCP_MAX))
ACTION = Operation(
    'action',
    _action,
    'sample|terminal|sample-terminal',
    ['sample', 'terminal', 'sample-terminal'],
    shape.enumeration('sample', 'terminal', 'sample-terminal'),
)
INTERFACE_SET = Operation(
    'interface-set',
    _interface_set,
    '<transitive>:<direction>:<asn>:<group>',
    ['input:1:1'],
    shape.leaf_list(shape.string(pattern=r'([a-z-]+:)?(input|output|input-output):\d+:\d+'), min_items=1),
)
FLOW_NEXTHOP = Operation(
    'next-hop',
    _flow_nexthop,
    '<ip>|self',
    ['10.0.0.1', 'self'],
    shape.union(shape.IP_ADDRESS, shape.enumeration('self')),
)
