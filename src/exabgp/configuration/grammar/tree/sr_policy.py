"""sr_policy.py

The SR policy route (RFC 9830), on one line:

    static { sr-policy distinguisher <n> color <n> endpoint <ip> next-hop <ip> [<sub-tlv> ...]; }
    announce { ipv4|ipv6 { sr-policy distinguisher <n> color <n> endpoint <ip> next-hop <ip> [...]; } }

    <sub-tlv>: preference <n> | priority <n> | enlp <name>|<1-4> | binding-sid mpls <label>|null
             | srv6-binding-sid <ipv6> | policy-name <text> | candidate-path-name <text>
             | segment-list weight <n> [segment <type> <fields> [verification] ...]

legacy: the sub-TLVs are read while the next word names one, and what follows them is ignored.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import contextlib
from typing import Any, Callable

from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.attribute.tunnel_encap import TunnelEncap
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy import (
    BindingSIDSubTLV,
    CandidatePathNameSubTLV,
    ENLPSubTLV,
    PolicyNameSubTLV,
    PreferenceSubTLV,
    PrioritySubTLV,
    SegmentListSubTLV,
    SRPolicyTunnel,
    SRv6BindingSIDSubTLV,
)
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.segment_list import (
    SegmentTypeA,
    SegmentTypeB,
    SegmentTypeC,
    SegmentTypeD,
    SegmentTypeE,
    SegmentTypeF,
    SegmentTypeG,
    SegmentTypeH,
    SegmentTypeI,
    SegmentTypeJ,
    SegmentTypeK,
    SRv6EndpointBehavior,
    WeightSubSubTLV,
)
from exabgp.bgp.message.update.nlri.sr_policy import SRPolicyNLRI
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.error import ROUTE_ERRORS, ConfigError
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.rib.route import Route

MPLS_LABEL_MAX = 1048575  # 2^20 - 1
MAX_SUBTLVS = 256  # a policy holds a handful of sub-TLVs
MAX_SEGMENTS = 256  # and a segment list a handful of segments
FLAG_V = 0x80  # SID verification, RFC 9830 section 2.4.4.2.3
FLAG_A = 0x40  # the algorithm is valid, RFC 9831 section 2.1
FLAG_B = 0x10  # the SRv6 endpoint behaviour is present

# RFC 9830 section 2.4.5
ENLP_VALUES = {'push-ipv4': 1, 'push-ipv6': 2, 'push-ipv4-ipv6': 3, 'no-push': 4}
ENLP_MAX = 4

Segment = (
    SegmentTypeA
    | SegmentTypeB
    | SegmentTypeC
    | SegmentTypeD
    | SegmentTypeE
    | SegmentTypeF
    | SegmentTypeG
    | SegmentTypeH
    | SegmentTypeI
    | SegmentTypeJ
    | SegmentTypeK
)


def _label(word: str, name: str) -> int:
    label = int(word)
    if label < 0 or label > MPLS_LABEL_MAX:
        raise ValueError(f'{name} {label} out of range (0-{MPLS_LABEL_MAX})')
    return label


def _mpls_sid(words: Words, checked: bool) -> int | None:
    """legacy: `sid <label>`, optional, its range checked for the types c, d and e only."""
    if words.peek() != 'sid':
        return None
    words.word()
    word = words.word()
    return _label(word, 'MPLS SID') if checked else int(word)


def _srv6_sid(words: Words) -> str | None:
    if words.peek() != 'sid':
        return None
    words.word()
    return words.word()


def _behaviour(words: Words) -> SRv6EndpointBehavior | None:
    """`endpoint-behavior <behaviour> <lb> <ln> <fun> <arg>`, optional."""
    if words.peek() != 'endpoint-behavior':
        return None
    words.word()
    behaviour = int(words.word(), 0)
    lb, ln, fun, arg = (int(words.word()) for _ in range(4))
    return SRv6EndpointBehavior(endpoint_behavior=behaviour, lb_length=lb, ln_length=ln, fun_length=fun, arg_length=arg)


def _flags(algorithm: int, behaviour: SRv6EndpointBehavior | None) -> int:
    return (FLAG_A if algorithm else 0) | (FLAG_B if behaviour is not None else 0)


def _field(words: Words, keyword: str) -> str:
    words.expect(keyword)
    return words.word()


def _field_number(words: Words, keyword: str) -> int:
    return int(_field(words, keyword))


def _type_a(words: Words) -> Segment:
    return SegmentTypeA(label=_label(_field(words, 'mpls'), 'MPLS label'))


def _type_b(words: Words) -> Segment:
    sid = _field(words, 'srv6')
    return SegmentTypeB(sid=sid, endpoint_behavior=_behaviour(words))


def _type_c(words: Words) -> Segment:
    node = _field(words, 'ipv4')
    algorithm = _field_number(words, 'algorithm')
    return SegmentTypeC(ipv4_node=node, algorithm=algorithm, flags=_flags(algorithm, None), sid=_mpls_sid(words, True))


def _type_d(words: Words) -> Segment:
    node = _field(words, 'ipv6')
    algorithm = _field_number(words, 'algorithm')
    return SegmentTypeD(ipv6_node=node, algorithm=algorithm, flags=_flags(algorithm, None), sid=_mpls_sid(words, True))


def _type_e(words: Words) -> Segment:
    local_if_id = _field_number(words, 'local-if-id')
    node = _field(words, 'ipv4')
    return SegmentTypeE(local_if_id=local_if_id, ipv4_node=node, sid=_mpls_sid(words, True))


def _type_f(words: Words) -> Segment:
    local, remote = _field(words, 'local'), _field(words, 'remote')
    return SegmentTypeF(local_ipv4=local, remote_ipv4=remote, sid=_mpls_sid(words, False))


def _interfaces(words: Words) -> dict[str, Any]:
    local_if_id = _field_number(words, 'local-if-id')
    local = _field(words, 'local-ipv6')
    remote_if_id = _field_number(words, 'remote-if-id')
    remote = _field(words, 'remote-ipv6')
    return {'local_if_id': local_if_id, 'local_ipv6': local, 'remote_if_id': remote_if_id, 'remote_ipv6': remote}


def _type_g(words: Words) -> Segment:
    interfaces = _interfaces(words)
    return SegmentTypeG(**interfaces, sid=_mpls_sid(words, False))


def _type_h(words: Words) -> Segment:
    local, remote = _field(words, 'local'), _field(words, 'remote')
    return SegmentTypeH(local_ipv6=local, remote_ipv6=remote, sid=_mpls_sid(words, False))


def _srv6_tail(words: Words) -> dict[str, Any]:
    """`algorithm <n> [sid <ipv6>] [endpoint-behavior ...]`, the tail of the types i, j and k."""
    algorithm = _field_number(words, 'algorithm')
    sid = _srv6_sid(words)
    behaviour = _behaviour(words)
    return {'algorithm': algorithm, 'flags': _flags(algorithm, behaviour), 'sid': sid, 'endpoint_behavior': behaviour}


def _type_i(words: Words) -> Segment:
    node = _field(words, 'ipv6')
    return SegmentTypeI(ipv6_node=node, **_srv6_tail(words))


def _type_j(words: Words) -> Segment:
    interfaces = _interfaces(words)
    return SegmentTypeJ(**interfaces, **_srv6_tail(words))


def _type_k(words: Words) -> Segment:
    local, remote = _field(words, 'local'), _field(words, 'remote')
    return SegmentTypeK(local_ipv6=local, remote_ipv6=remote, **_srv6_tail(words))


SEGMENTS: dict[str, Callable[[Words], Segment]] = {
    'type-a': _type_a,
    'type-b': _type_b,
    'type-c': _type_c,
    'type-d': _type_d,
    'type-e': _type_e,
    'type-f': _type_f,
    'type-g': _type_g,
    'type-h': _type_h,
    'type-i': _type_i,
    'type-j': _type_j,
    'type-k': _type_k,
}


def _segment_list(words: Words) -> SegmentListSubTLV:
    weight = WeightSubSubTLV(weight=_field_number(words, 'weight'))
    segments: list[Segment] = []
    for _ in range(MAX_SEGMENTS):
        if words.peek() != 'segment':
            return SegmentListSubTLV(weight=weight, segments=segments)
        words.word()
        kind = words.word()
        reader = SEGMENTS.get(kind)
        if reader is None:
            raise ValueError(f"Unknown segment type '{kind}'. Expected: {', '.join(SEGMENTS)}")
        segments.append(reader(words))
        if words.peek() == 'verification':
            words.word()
            segments[-1].flags |= FLAG_V
    raise ValueError(f'a segment list holds at most {MAX_SEGMENTS} segments')


def _enlp(words: Words) -> ENLPSubTLV:
    word = words.word()
    if word in ENLP_VALUES:
        return ENLPSubTLV(enlp=ENLP_VALUES[word])
    if word.isdigit() and 1 <= int(word) <= ENLP_MAX:
        return ENLPSubTLV(enlp=int(word))
    raise ValueError(f"Unknown enlp value '{word}'. Expected: {', '.join(ENLP_VALUES)} or 1-{ENLP_MAX}")


def _binding_sid(words: Words) -> BindingSIDSubTLV:
    kind = words.word()
    if kind == 'mpls':
        return BindingSIDSubTLV(label=int(words.word()))
    if kind == 'null':
        return BindingSIDSubTLV(label=None)
    raise ValueError(f"Unknown binding-sid type '{kind}'. Expected: mpls, null")


def _name(words: Words) -> str:
    return words.word().strip('"').strip("'")


SUBTLVS: dict[str, Callable[[Words], Any]] = {
    'preference': lambda words: PreferenceSubTLV(preference=int(words.word())),
    'priority': lambda words: PrioritySubTLV(priority=int(words.word())),
    'enlp': _enlp,
    'binding-sid': _binding_sid,
    'srv6-binding-sid': lambda words: SRv6BindingSIDSubTLV(sid=words.word()),
    'policy-name': lambda words: PolicyNameSubTLV(name=_name(words)),
    'candidate-path-name': lambda words: CandidatePathNameSubTLV(name=_name(words)),
    'segment-list': _segment_list,
}


def _subtlvs(words: Words) -> list[Any]:
    subtlvs: list[Any] = []
    for _ in range(MAX_SUBTLVS):
        key = words.peek()
        if key not in SUBTLVS:
            return subtlvs
        words.word()
        if key == 'enlp' and any(isinstance(subtlv, ENLPSubTLV) for subtlv in subtlvs):
            raise ValueError('ENLP sub-TLV may appear only once')
        subtlvs.append(SUBTLVS[key](words))
    raise ValueError(f'a policy holds at most {MAX_SUBTLVS} sub-TLVs')


def _endpoint_afi(word: str) -> AFI:
    """legacy: the static section takes the family of the endpoint, IPv4 when it has none."""
    afi = AFI.ipv4
    with contextlib.suppress(ValueError):
        afi = IP.toafi(word)
    return afi


def sr_policy_route(words: Words, afi: AFI | None) -> Route:
    """`afi` is None in the static section, where the endpoint gives it."""
    distinguisher = _field_number(words, 'distinguisher')
    color = _field_number(words, 'color')
    endpoint = _field(words, 'endpoint')
    route_afi = _endpoint_afi(endpoint) if afi is None else afi
    nlri = SRPolicyNLRI.create(afi=route_afi, distinguisher=distinguisher, color=color, endpoint=endpoint)
    nexthop = IP.from_string(_field(words, 'next-hop'))
    subtlvs = _subtlvs(words)
    attributes = AttributeCollection()
    if subtlvs:
        attributes.add(TunnelEncap(tunnel_tlvs=[SRPolicyTunnel(subtlvs=subtlvs)]))
    # legacy: whatever the sub-TLVs are followed by is not read
    words.rest()
    return Route(nlri, attributes, nexthop=nexthop)


class SRPolicyLine(Type[list[Route]]):
    """`distinguisher <n> color <n> endpoint <ip> next-hop <ip> [<sub-tlv> ...]`."""

    def __init__(self, afi: AFI | None) -> None:
        self.afi = afi
        self.name = 'sr-policy route'

    def parse(self, words: Words) -> list[Route]:
        where = words.where()
        try:
            return [sr_policy_route(words, self.afi)]
        except ConfigError:
            raise  # positioned already, by the value which failed
        except ROUTE_ERRORS as exc:
            raise ConfigError(where, str(exc) or 'invalid sr-policy route') from None

    def render(self, value: list[Route]) -> list[str]:
        return [word for route in value for word in sr_policy_words(route)]

    def hint(self) -> str:
        return 'distinguisher <n> color <n> endpoint <ip> next-hop <ip> [<sub-tlv> ...]'

    def examples(self) -> list[str]:
        return []

    def shape(self) -> Shape:
        return SR_POLICY


# --------------------------------------------------------------------------- the data model

_LABEL = shape.integer(0, MPLS_LABEL_MAX)
_ALGORITHM = ('algorithm', shape.UINT8.described('the SR algorithm, RFC 8402'))
_BEHAVIOUR = (
    'endpoint-behavior',
    shape.container(
        ('behavior', shape.UINT16.described('the endpoint behaviour, RFC 8986')),
        ('locator-block', shape.UINT8.described('the length of the locator block, in bits')),
        ('locator-node', shape.UINT8.described('the length of the locator node, in bits')),
        ('function', shape.UINT8.described('the length of the function, in bits')),
        ('argument', shape.UINT8.described('the length of the argument, in bits')),
    ).described('the SRv6 endpoint behaviour and SID structure'),
)
_INTERFACES = (
    ('local-if-id', shape.UINT32.described('the local interface identifier')),
    ('local-ipv6', shape.IPV6_ADDRESS.described('the local IPv6 address')),
    ('remote-if-id', shape.UINT32.described('the remote interface identifier')),
    ('remote-ipv6', shape.IPV6_ADDRESS.described('the remote IPv6 address')),
)
_MPLS_SID = ('sid', _LABEL.described('the MPLS label of the segment'))
_NUMBER_SID = ('sid', shape.UINT32.described('the MPLS label of the segment'))
_SRV6_TAIL = (_ALGORITHM, ('sid', shape.IPV6_ADDRESS.described('the SRv6 SID of the segment')), _BEHAVIOUR)
_LOCAL4 = ('local', shape.IPV4_ADDRESS.described('the local IPv4 address'))
_REMOTE4 = ('remote', shape.IPV4_ADDRESS.described('the remote IPv4 address'))
_LOCAL6 = ('local', shape.IPV6_ADDRESS.described('the local IPv6 address'))
_REMOTE6 = ('remote', shape.IPV6_ADDRESS.described('the remote IPv6 address'))
_NODE4 = ('ipv4', shape.IPV4_ADDRESS.described('the IPv4 node address'))
_NODE6 = ('ipv6', shape.IPV6_ADDRESS.described('the IPv6 node address'))
_VERIFICATION = ('verification', shape.empty().described('verify the SID, the V-flag, RFC 9830 2.4.4.2.3'))
# each segment type, what it is and the fields it reads, RFC 9830 2.4.4.2 and RFC 9831
SEGMENT_FIELDS: dict[str, tuple[str, tuple[tuple[str, Shape], ...]]] = {
    'type-a': ('an MPLS label', (('mpls', _LABEL.described('the MPLS label')),)),
    'type-b': ('an SRv6 SID', (('srv6', shape.IPV6_ADDRESS.described('the SRv6 SID')), _BEHAVIOUR)),
    'type-c': ('an IPv4 node, with an optional MPLS SID', (_NODE4, _ALGORITHM, _MPLS_SID)),
    'type-d': ('an IPv6 node, with an optional MPLS SID', (_NODE6, _ALGORITHM, _MPLS_SID)),
    'type-e': (
        'an IPv4 node and a local interface, with an optional MPLS SID',
        (('local-if-id', shape.UINT32.described('the local interface identifier')), _NODE4, _MPLS_SID),
    ),
    'type-f': ('an IPv4 adjacency, with an optional MPLS SID', (_LOCAL4, _REMOTE4, _NUMBER_SID)),
    'type-g': ('an IPv6 adjacency by interface, with an optional MPLS SID', (*_INTERFACES, _NUMBER_SID)),
    'type-h': ('an IPv6 adjacency, with an optional MPLS SID', (_LOCAL6, _REMOTE6, _NUMBER_SID)),
    'type-i': ('an IPv6 node, with an optional SRv6 SID', (_NODE6, *_SRV6_TAIL)),
    'type-j': ('an IPv6 adjacency by interface, with an optional SRv6 SID', (*_INTERFACES, *_SRV6_TAIL)),
    'type-k': ('an IPv6 adjacency, with an optional SRv6 SID', (_LOCAL6, _REMOTE6, *_SRV6_TAIL)),
}
_SEGMENT = shape.choice(
    *((kind, shape.container(*fields, _VERIFICATION).described(doc)) for kind, (doc, fields) in SEGMENT_FIELDS.items())
)
_SEGMENT_LIST = shape.container(
    ('weight', shape.UINT32.described('the weight of the list, among the lists of the path')),
    ('segment', shape.leaf_list(_SEGMENT).described('the segments, in order')),
)
SR_POLICY = shape.container(
    ('distinguisher', shape.UINT32.described('makes the NLRI unique, RFC 9830 2.1')),
    ('color', shape.UINT32.described('the color of the policy')),
    ('endpoint', shape.IP_ADDRESS.described('the endpoint of the policy')),
    ('next-hop', shape.IP_ADDRESS.described('the next-hop of the route')),
    ('preference', shape.UINT32.described('the preference of the candidate path')),
    ('priority', shape.UINT8.described('the order in which the policy is recomputed')),
    (
        'enlp',
        shape.union(shape.enumeration(*ENLP_VALUES), shape.integer(1, ENLP_MAX)).described(
            'the explicit null label policy, RFC 9830 2.4.5'
        ),
    ),
    (
        'binding-sid',
        shape.union(_LABEL, shape.enumeration('null')).described('the MPLS binding SID, or null for none'),
    ),
    ('srv6-binding-sid', shape.IPV6_ADDRESS.described('the SRv6 binding SID')),
    ('policy-name', shape.TEXT.described('the name of the policy')),
    ('candidate-path-name', shape.TEXT.described('the name of the candidate path')),
    ('segment-list', shape.leaf_list(_SEGMENT_LIST).described('the segment lists of the candidate path')),
).described('an SR policy, RFC 9830')


# --------------------------------------------------------------------------- printing


def _behaviour_words(behaviour: SRv6EndpointBehavior | None) -> list[str]:
    if behaviour is None:
        return []
    fields = (behaviour.lb_length, behaviour.ln_length, behaviour.fun_length, behaviour.arg_length)
    return ['endpoint-behavior', str(behaviour.endpoint_behavior), *(str(field) for field in fields)]


def _sid_words(sid: Any) -> list[str]:
    return [] if sid is None else ['sid', str(sid)]


def _interface_words(segment: Any) -> list[str]:
    return [
        *('local-if-id', str(segment.local_if_id), 'local-ipv6', str(segment.local_ipv6)),
        *('remote-if-id', str(segment.remote_if_id), 'remote-ipv6', str(segment.remote_ipv6)),
    ]


def _srv6_words(segment: Any) -> list[str]:
    return ['algorithm', str(segment.algorithm), *_sid_words(segment.sid), *_behaviour_words(segment.endpoint_behavior)]


def _segment_fields(segment: Any) -> list[str]:
    if isinstance(segment, SegmentTypeA):
        return ['type-a', 'mpls', str(segment.label)]
    if isinstance(segment, SegmentTypeB):
        return ['type-b', 'srv6', str(segment.sid), *_behaviour_words(segment.endpoint_behavior)]
    if isinstance(segment, SegmentTypeC):
        return ['type-c', 'ipv4', str(segment.ipv4_node), 'algorithm', str(segment.algorithm), *_sid_words(segment.sid)]
    if isinstance(segment, SegmentTypeD):
        return ['type-d', 'ipv6', str(segment.ipv6_node), 'algorithm', str(segment.algorithm), *_sid_words(segment.sid)]
    if isinstance(segment, SegmentTypeE):
        local = ['local-if-id', str(segment.local_if_id)]
        return ['type-e', *local, 'ipv4', str(segment.ipv4_node), *_sid_words(segment.sid)]
    if isinstance(segment, SegmentTypeF):
        return ['type-f', 'local', segment.local_ipv4, 'remote', segment.remote_ipv4, *_sid_words(segment.sid)]
    if isinstance(segment, SegmentTypeH):
        return ['type-h', 'local', segment.local_ipv6, 'remote', segment.remote_ipv6, *_sid_words(segment.sid)]
    if isinstance(segment, SegmentTypeG):
        return ['type-g', *_interface_words(segment), *_sid_words(segment.sid)]
    if isinstance(segment, SegmentTypeI):
        return ['type-i', 'ipv6', str(segment.ipv6_node), *_srv6_words(segment)]
    if isinstance(segment, SegmentTypeJ):
        return ['type-j', *_interface_words(segment), *_srv6_words(segment)]
    if isinstance(segment, SegmentTypeK):
        return ['type-k', 'local', str(segment.local_ipv6), 'remote', str(segment.remote_ipv6), *_srv6_words(segment)]
    raise ValueError(f'no statement writes a {type(segment).__name__} segment')


def _segment_words(segment: Any) -> list[str]:
    words = ['segment', *_segment_fields(segment)]
    return words + (['verification'] if segment.flags & FLAG_V else [])


def _subtlv_words(subtlv: Any) -> list[str]:
    if isinstance(subtlv, PreferenceSubTLV):
        return ['preference', str(subtlv.preference)]
    if isinstance(subtlv, PrioritySubTLV):
        return ['priority', str(subtlv.priority)]
    if isinstance(subtlv, ENLPSubTLV):
        return ['enlp', str(subtlv.enlp)]
    if isinstance(subtlv, BindingSIDSubTLV):
        return ['binding-sid', 'null'] if subtlv.label is None else ['binding-sid', 'mpls', str(subtlv.label)]
    if isinstance(subtlv, SRv6BindingSIDSubTLV):
        return ['srv6-binding-sid', str(subtlv.sid)]
    if isinstance(subtlv, PolicyNameSubTLV):
        return ['policy-name', subtlv.name]
    if isinstance(subtlv, CandidatePathNameSubTLV):
        return ['candidate-path-name', subtlv.name]
    if isinstance(subtlv, SegmentListSubTLV):
        segments = [word for segment in subtlv.segments for word in _segment_words(segment)]
        return ['segment-list', 'weight', str(subtlv.weight.weight), *segments]
    raise ValueError(f'no statement writes a {type(subtlv).__name__} sub-TLV')


def _tunnel(route: Route) -> SRPolicyTunnel | None:
    attributes = list(route.attributes.values())
    if not attributes:
        return None
    if len(attributes) != 1 or not isinstance(attributes[0], TunnelEncap):
        raise ValueError('an sr-policy route holds no attribute but its tunnel encapsulation')
    tlvs = attributes[0].tunnel_tlvs
    if len(tlvs) != 1 or not isinstance(tlvs[0], SRPolicyTunnel) or not tlvs[0].subtlvs:
        raise ValueError('an sr-policy route holds one SR policy tunnel')
    tunnel: SRPolicyTunnel = tlvs[0]
    return tunnel


def sr_policy_words(route: Route) -> list[str]:
    """What follows `sr-policy`: the NLRI, the next-hop, the sub-TLVs in the order they were read."""
    nlri: Any = route.nlri
    words = ['distinguisher', str(nlri.distinguisher), 'color', str(nlri.color), 'endpoint', nlri.endpoint]
    words += ['next-hop', str(route.nexthop)]
    tunnel = _tunnel(route)
    if tunnel is not None:
        words += [word for subtlv in tunnel.subtlvs for word in _subtlv_words(subtlv)]
    return words
