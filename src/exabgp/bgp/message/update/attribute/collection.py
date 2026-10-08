"""BGP path attribute collections (semantic and wire containers).

This module provides two container types for BGP path attributes:

AttributeCollection: Semantic container (dict-like)
    - Stores parsed Attribute objects by code
    - Used for building routes and modifying attributes
    - Provides text/JSON serialization

Attributes: Wire container (bytes-first)
    - Stores raw packed attribute bytes
    - Lazy parsing via iterator
    - Used for efficient message handling

See .claude/exabgp/WIRE_SEMANTIC_SEPARATION.md for design rationale.

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
import re
from struct import unpack
from collections.abc import Callable, Iterator, MutableMapping
from typing import TYPE_CHECKING, Any, ClassVar, Generator, cast

from exabgp.util.types import Buffer
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.util.intvalue import json_number

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


from exabgp.bgp.message.notification import Notify, TreatAsWithdrawNotify
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.aspath import (
    CONFED_SEQUENCE,
    CONFED_SET,
    SEQUENCE,
    SET,
    AS2Path,
    ASPath,
    PathSegment,
)
from exabgp.bgp.message.update.attribute.attribute import (
    Attribute,
    Discard,
    TreatAsWithdraw,
)

# For bagpipe
from exabgp.bgp.message.update.attribute.community import Communities, Community
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget
from exabgp.bgp.message.update.attribute.community.extended.communities import (
    ExtendedCommunities,
    ExtendedCommunitiesBase,
)
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.otc import OTCSelf
from exabgp.bgp.message.update.attribute.watchdog import NoWatchdog, Watchdog
from exabgp.logger import lazyattribute, lazymsg, log

# The integer grammar of RFC 8259 section 6: an optional minus, then either a single zero
# or a digit which is not zero followed by any digits. No plus, no leading zero, no
# separator, all three of which Python's int() would accept.
_JSON_INTEGER = re.compile(r'-?(?:0|[1-9][0-9]*)')


# The T bit is cleared, the I bit kept: see RouteTarget.TYPE_MASK, which RTC.admits shares.
ROUTE_TARGET_TYPE_MASK = RouteTarget.TYPE_MASK
ROUTE_TARGET_SUBTYPE = 0x02
# two-octet AS, IPv4 address, four-octet AS
ROUTE_TARGET_TYPES = (0x00, 0x01, 0x02)

# The attributes made of extended communities, each of which has a T bit (RFC 4360 2, RFC 5701 2).
EXTENDED_COMMUNITY_CODES = (Attribute.CODE.EXTENDED_COMMUNITY, Attribute.CODE.IPV6_EXTENDED_COMMUNITY)


class _NOTHING:
    def pack(self, _: Any = None) -> bytes:
        return b''

    def pack_attribute(self, _: Any = None) -> bytes:
        return b''


NOTHING: _NOTHING = _NOTHING()


def in_type_order(packed: bytes) -> bytes:
    """A run of attributes we packed, put in ascending order of type code.

    RFC 4271 5: "The sender of an UPDATE message SHOULD order path attributes within the
    UPDATE message in ascending order of attribute type."  Most attributes are packed in
    that order already, but some are packed together with another (AS_PATH with AS4_PATH,
    AGGREGATOR with AS4_AGGREGATOR) and the OTC of RFC 9234 is added once the rest is
    packed. The sort is stable, so nothing else moves.

    The bytes are ours, never a peer's, so a header or value cut short is our own bug: it
    raises RuntimeError rather than asserting, so it holds under -O as well.
    """
    attributes: list[tuple[int, bytes]] = []
    offset = 0
    # bounded: each pass moves past one whole attribute, header and value
    while offset < len(packed):
        if offset + 3 > len(packed):
            raise RuntimeError('an attribute we packed has a truncated header')
        flag, code = packed[offset], packed[offset + 1]
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            end = offset + 4 + int.from_bytes(packed[offset + 2 : offset + 4], 'big')
        else:
            end = offset + 3 + packed[offset + 2]
        if end > len(packed):
            raise RuntimeError('an attribute we packed runs past the attributes')
        attributes.append((code, packed[offset:end]))
        offset = end
    codes = [code for code, _ in attributes]
    if codes == sorted(codes):
        return packed
    return b''.join(attribute for _, attribute in sorted(attributes, key=lambda pair: pair[0]))


# =================================================================== AttributeCollection


# RFC 4271 6.3: for these subcodes "The Data field MUST contain the ... attribute (type,
# length, and value)".  3/3 is not here: its Data field is only the missing type code
_DATA_IS_THE_ATTRIBUTE: frozenset[tuple[int, int]] = frozenset({(3, 2), (3, 4), (3, 5), (3, 6), (3, 8), (3, 9)})


def _with_the_attribute(notify: Notify, header: Buffer, value: Buffer) -> Notify:
    """The same Notify, carrying the attribute it is about as its Data field.

    The per-attribute decoders only see the value, so they cannot fill it themselves.
    """
    if notify.has_defined_data or (notify.code, notify.subcode) not in _DATA_IS_THE_ATTRIBUTE:
        return notify
    return Notify(notify.code, notify.subcode, notify.detail, data=bytes(header) + bytes(value))


# RFC 7606 7.5, 7.9 and 7.10: the attributes discarded when they arrive from an external
# neighbour, as they only have a meaning inside the AS (or the confederation).
_INTERNAL_ONLY: frozenset[int] = frozenset(
    {Attribute.CODE.LOCAL_PREF, Attribute.CODE.ORIGINATOR_ID, Attribute.CODE.CLUSTER_LIST}
)


# The two attributes RFC 7606 3 (j) needs parsed before treat-as-withdraw can be used. One
# which cannot be framed or is too short is never withdrawn around: RFC 4760 7 and RFC 7606
# 5.3 make it 3/9, "UPDATE Message Error"/"Optional Attribute Error", with the attribute as
# the Data field (RFC 4271 6.3).
_MP_CODES: frozenset[int] = frozenset({Attribute.CODE.MP_REACH_NLRI, Attribute.CODE.MP_UNREACH_NLRI})

# What AttributeCollection.parse did about a malformed attribute, as recorded in malformed.
TREAT_AS_WITHDRAW_ACTION = 'treat-as-withdraw'
ATTRIBUTE_DISCARD_ACTION = 'attribute-discard'
# RFC 4760 3: a NEXT_HOP beside MP_REACH_NLRI alone is ignored, malformed or not.
NEXT_HOP_IGNORED_ACTION = 'ignored'


def _unframed_mp_attribute(aid: int, reason: str, attribute: Buffer) -> Notify:
    """An MP_REACH_NLRI or MP_UNREACH_NLRI which cannot be framed, so its NLRI cannot be read."""
    return Notify(3, 9, f'{Attribute.CODE.name(aid)} {reason}', data=bytes(attribute))


class AttributeCollection(MutableMapping[int, Attribute]):
    """Semantic container for BGP path attributes (dict-like).

    Stores parsed Attribute objects indexed by attribute code.
    Used for route construction, modification, and serialization.

    Wire format header: [flags(1)][type_code(1)][length(1-2)][value...]
    """

    # Internal pseudo-attributes are process decisions, never wire attributes.
    INTERNAL: ClassVar[tuple[int, ...]] = (
        Attribute.CODE.INTERNAL_SPLIT,
        Attribute.CODE.INTERNAL_WATCHDOG,
        Attribute.CODE.INTERNAL_NAME,
        Attribute.CODE.INTERNAL_WITHDRAW,
        Attribute.CODE.INTERNAL_DISCARD,
        Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW,
        Attribute.CODE.INTERNAL_OTC_NONE,
    )
    INTERNAL_IDENTITY: ClassVar[tuple[int, ...]] = (Attribute.CODE.INTERNAL_OTC_NONE,)

    # The previously parsed AttributeCollection, and the bytes it was made from, are kept
    # on the Negotiated of the session they belong to. They used to be ClassVars: one slot
    # for the whole process, keyed on the wire bytes alone. Several attributes decode
    # against what the session negotiated (AIGP returns a Discard when the session did not
    # negotiate it, AS_PATH and AGGREGATOR read differently under ASN4), so two peers
    # sending identical bytes had the second handed the first one's interpretation. See
    # unpack() and tests/unit/test_attribute_cache_per_session.py.

    representation: ClassVar[dict[int, tuple[str, str, str, str, str]]] = {
        # key:  (how, default, name, text_presentation, json_presentation),
        Attribute.CODE.ORIGIN: ('string', '', 'origin', '%s', '%s'),
        Attribute.CODE.AS_PATH: ('list', '', 'as-path', '%s', '%s'),
        Attribute.CODE.NEXT_HOP: ('string', '', 'next-hop', '%s', '%s'),
        Attribute.CODE.MED: ('integer', '', 'med', '%s', '%s'),
        Attribute.CODE.LOCAL_PREF: ('integer', '', 'local-preference', '%s', '%s'),
        Attribute.CODE.ATOMIC_AGGREGATE: ('boolean', '', 'atomic-aggregate', '%s', '%s'),
        Attribute.CODE.AGGREGATOR: ('string', '', 'aggregator', '( %s )', '%s'),
        Attribute.CODE.AS4_AGGREGATOR: ('string', '', 'aggregator', '( %s )', '%s'),
        Attribute.CODE.COMMUNITY: ('list', '', 'community', '%s', '%s'),
        Attribute.CODE.LARGE_COMMUNITY: ('list', '', 'large-community', '%s', '%s'),
        Attribute.CODE.ORIGINATOR_ID: ('inet', '', 'originator-id', '%s', '%s'),
        Attribute.CODE.CLUSTER_LIST: ('list', '', 'cluster-list', '%s', '%s'),
        Attribute.CODE.EXTENDED_COMMUNITY: ('list', '', 'extended-community', '%s', '%s'),
        Attribute.CODE.IPV6_EXTENDED_COMMUNITY: ('list', '', 'extended-community-ipv6', '%s', '%s'),
        Attribute.CODE.PMSI_TUNNEL: ('string', '', 'pmsi', '%s', '%s'),
        Attribute.CODE.AIGP: ('integer', '', 'aigp', '%s', '%s'),
        Attribute.CODE.OTC: ('integer', '', 'otc', '%s', '%s'),
        Attribute.CODE.BGP_LS: ('list', '', 'bgp-ls', '%s', '%s'),
        Attribute.CODE.BGP_PREFIX_SID: ('list', '', 'bgp-prefix-sid', '%s', '%s'),
        Attribute.CODE.TUNNEL_ENCAP: ('list', '', 'tunnel-encap', '%s', '%s'),
        Attribute.CODE.INTERNAL_NAME: ('string', '', 'name', '%s', '%s'),
        Attribute.CODE.INTERNAL_DISCARD: ('string', '', 'error', '%s', '%s'),
        Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW: ('string', '', 'error', '%s', '%s'),
    }

    _str: str
    _idx: bytes
    _json: str
    cacheable: bool
    learned_from: str
    malformed: list[tuple[int, str, str]]
    next_hop_malformed: str

    def _generate_text(self) -> Generator[str, None, None]:
        for code in sorted(self.keys()):
            # Skip internal pseudo-attributes
            if code in AttributeCollection.INTERNAL:
                continue

            attribute = self[code]

            # Skip attributes marked as NO_GENERATION:
            # - Internal pseudo-attributes (TreatAsWithdraw, Discard)
            # - NextHop: output with NLRI, not as separate attribute
            if attribute.NO_GENERATION:
                continue

            if code not in self.representation:
                yield ' attribute [ 0x{:02X} 0x{:02X} {} ]'.format(code, attribute.FLAG, str(attribute))
                continue

            if attribute.GENERIC:
                yield ' attribute [ 0x{:02X} 0x{:02X} {} ]'.format(code, attribute.FLAG, str(attribute))
                continue

            how, _, name, presentation, _ = self.representation[code]
            if how == 'boolean':
                yield ' {}'.format(name)
            elif how == 'list':
                value = str(attribute)
                if value:  # Skip empty lists (e.g., empty AS_PATH)
                    yield ' {} {}'.format(name, presentation % value)
            else:
                yield ' {} {}'.format(name, presentation % str(attribute))

    @staticmethod
    def _as_json_scalar(text: str) -> str:
        """Emit a number as a number, and anything else as a quoted string.

        The test used to be `int(text)`, which accepts more than JSON does: '010', '00',
        '1_000' and '+5' all parse in Python and none of them is a JSON number, so each
        was emitted bare and made the whole line unparseable for the consumer. Only the
        integer grammar of RFC 8259 section 6 goes out unquoted.
        """
        if _JSON_INTEGER.fullmatch(text.strip()):
            return text
        return json.dumps(text, default=json_number)

    def _generate_json(self, include_nexthop: bool = False, generic: bool = False) -> Generator[str, None, None]:
        for code in sorted(self.keys()):
            # Skip internal pseudo-attributes
            if code in AttributeCollection.INTERNAL:
                continue

            attribute = self[code]

            # Skip attributes marked as NO_GENERATION:
            # - Internal pseudo-attributes (TreatAsWithdraw, Discard) that aren't real BGP attributes
            # - NextHop: output with NLRI in announce (as "nexthop" key)
            #   For withdraws, include_nexthop=True includes NEXT_HOP in attributes
            if attribute.NO_GENERATION:
                if not (include_nexthop and code == Attribute.CODE.NEXT_HOP):
                    continue

            if code not in self.representation:
                # For generic mode, output hex; otherwise use str() which may be human-readable
                if generic and hasattr(attribute, '_packed'):
                    hex_value = '0x' + attribute._packed.hex()
                    yield '"attribute-0x{:02X}-0x{:02X}": {}'.format(
                        code, attribute.FLAG, json.dumps(hex_value, default=json_number)
                    )
                else:
                    yield '"attribute-0x{:02X}-0x{:02X}": {}'.format(code, attribute.FLAG, json.dumps(str(attribute)))
                continue

            how, _, name, _, presentation = self.representation[code]
            if how == 'boolean':
                yield '"{}": {}'.format(name, 'true' if self.has(code) else 'false')
            elif how == 'integer':
                # MED and local preference print as decimal, which is a JSON number, but
                # AIGP prints as 0x000000000000000a, which is not: unquoted it made the
                # line unparseable. Whether the text is a number decides how it is emitted.
                yield '"{}": {}'.format(name, self._as_json_scalar(presentation % str(attribute)))
            elif how == 'string':
                yield '"{}": {}'.format(name, json.dumps(presentation % str(attribute), default=json_number))
            elif how == 'list':
                json_value = attribute.json()
                if json_value != '{}':  # Skip empty lists (e.g., empty AS_PATH)
                    yield '"{}": {}'.format(name, presentation % json_value)
            elif how == 'inet':
                yield '"{}": {}'.format(name, json.dumps(presentation % str(attribute), default=json_number))
            # Should never be ran
            else:
                yield '"{}": {}'.format(name, presentation % str(attribute))

    def __init__(self) -> None:
        self._data: dict[int, Attribute] = {}
        # cached representation of the object
        self._str = ''
        self._idx = b''
        self._json = ''
        # The parsed attributes have no mp routes and/or those are last
        self.cacheable = True
        # The address of the peer these attributes were decoded from, '' for a route we
        # originate. RFC 1997, RFC 4360 and RFC 7911 bind a route received from a peer and
        # re-advertised, never one the configuration or the API gave us.
        self.learned_from = ''
        # RFC 7606 6: what parse() found malformed and did about it, as (attribute code,
        # action, reason). The UPDATE logs it, once, with its NLRI and its bytes: only the
        # UPDATE knows those. Bounded by the attributes parsed, one entry at most each.
        self.malformed: list[tuple[int, str, str]] = []
        # Why the NEXT_HOP attribute was malformed, '' when it was not. RFC 7606 7.3 makes it
        # treat-as-withdraw, but RFC 4760 3 has it ignored in an UPDATE whose only NLRI are
        # in MP_REACH_NLRI, so the UPDATE, which knows which it is, decides.
        self.next_hop_malformed = ''
        # Note: Attribute.caching is set in application/server.py at startup

    # MutableMapping abstract methods

    def __getitem__(self, key: int) -> Attribute:
        return self._data[key]

    def __setitem__(self, key: int, value: Attribute) -> None:
        self._data[key] = value

    def __delitem__(self, key: int) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[int]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def has(self, k: int) -> bool:
        return k in self._data

    def add(self, attribute: Attribute | None, _: Any = None) -> None:
        # we return None as attribute if the unpack code must not generate them
        if attribute is None:
            return

        if attribute.ID in self:
            if attribute.ID != Attribute.CODE.EXTENDED_COMMUNITY:
                # attempting to add duplicate attribute when not allowed
                return

            self._str = ''
            self._json = ''

            # attribute.ID is EXTENDED_COMMUNITY, so attribute is ExtendedCommunitiesBase
            assert isinstance(attribute, ExtendedCommunitiesBase)
            existing = self[attribute.ID]
            assert isinstance(existing, ExtendedCommunitiesBase)
            for community in attribute.communities:
                existing.add(community)
            return

        self._str = ''
        self._json = ''
        self[attribute.ID] = attribute

    def copy(self) -> AttributeCollection:
        """A shallow copy: a new mapping over the same attribute objects.

        Callers copy in order to change the mapping without changing the original,
        which is why the derived text, json and index caches start empty here rather
        than being carried over: they describe the mapping this copy is about to stop
        matching. The attributes themselves are immutable and so are shared.
        """
        duplicate = AttributeCollection()
        duplicate._data = dict(self._data)
        duplicate.cacheable = self.cacheable
        duplicate.learned_from = self.learned_from
        duplicate.malformed = list(self.malformed)
        duplicate.next_hop_malformed = self.next_hop_malformed
        assert len(duplicate) == len(self), 'a copy holds every attribute of its original'
        return duplicate

    def remove(self, attrid: int) -> None:
        self.pop(attrid)

    def watchdog(self) -> Watchdog:
        value = self.pop(Attribute.CODE.INTERNAL_WATCHDOG, None)
        if value is None:
            return NoWatchdog
        return Watchdog(str(value))

    def withdraw(self) -> bool:
        return self.pop(Attribute.CODE.INTERNAL_WITHDRAW, None) is not None

    def otc_allowed(self, negotiated: Negotiated, family: FamilyTuple) -> bool:
        otc = self.get(Attribute.CODE.OTC)
        if isinstance(otc, OTCSelf) and otc.role != RoleValue.NO_ROLE and otc.role != negotiated.role:
            return False
        return not (
            Attribute.CODE.OTC in self
            and negotiated.role in (RoleValue.CUSTOMER, RoleValue.RS_CLIENT, RoleValue.PEER)
            and family in ((AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast))
        )

    def route_targets(self) -> list[bytes]:
        """The Route Targets carried, eight octets each, the T bit cleared so either form matches."""
        if Attribute.CODE.EXTENDED_COMMUNITY not in self:
            return []
        # the attribute stored under EXTENDED_COMMUNITY is the EXTENDED_COMMUNITY attribute
        communities = cast(ExtendedCommunities, self[Attribute.CODE.EXTENDED_COMMUNITY])
        targets = []
        for community in communities.communities:
            packed = bytes(community.pack())
            kind = packed[0] & ROUTE_TARGET_TYPE_MASK
            # RFC 4360 4, RFC 5668: the three Route Targets share sub-type 0x02
            if packed[1] == ROUTE_TARGET_SUBTYPE and kind in ROUTE_TARGET_TYPES:
                targets.append(bytes([kind]) + packed[1:])
        return targets

    def community_forbids(self, negotiated: Negotiated) -> str:
        """The RFC 1997 well-known community keeping this route from the peer, '' if none.

        Only a received route is bound: the RFC speaks of "routes received carrying" the
        value. A route we originate with no-export towards a transit is how an operator
        asks that transit not to propagate it (RTBH, traffic engineering), and must go out.
        """
        if not self.learned_from:
            return ''
        if Attribute.CODE.COMMUNITY not in self:
            return ''
        # the attribute stored under COMMUNITY is the COMMUNITY attribute
        communities = cast(Communities, self[Attribute.CODE.COMMUNITY])
        carried = {bytes(community.community) for community in communities.communities}
        if Community.NO_ADVERTISE in carried:
            return 'no-advertise'
        # NO_EXPORT stops at the confederation boundary, a neighbouring Member-AS is inside it
        if Community.NO_EXPORT in carried and not negotiated.is_internal_neighbor:
            return 'no-export'
        # NO_EXPORT_SUBCONFED stops at our own Member-AS, so every EBGP neighbour is outside
        if Community.NO_EXPORT_SUBCONFED in carried and not negotiated.is_ibgp:
            return 'no-export-subconfed'
        return ''

    @staticmethod
    def _default_attributes(negotiated: Negotiated) -> dict[int, Callable[[], Attribute | _NOTHING]]:
        """What a route without ORIGIN, AS_PATH or LOCAL_PREF is sent with, by where the peer is.

        RFC 5065 4.1 for an originated route: an empty AS_PATH inside our own AS, our
        Member-AS in an AS_CONFED_SEQUENCE to another member of the confederation, and our
        AS (the confederation identifier once in one) in an AS_SEQUENCE to anyone else.
        RFC 5065 5.2 lets LOCAL_PREF go to another member as it goes inside our own AS.
        """
        local_asn = negotiated.local_as
        internal = local_asn == negotiated.peer_as
        member = not internal and negotiated.confed_member

        def as_path() -> Attribute:
            if internal:
                return AS2Path.make_aspath([])
            segment = CONFED_SEQUENCE([local_asn]) if member else SEQUENCE([local_asn])
            return AS2Path.make_aspath([segment], asn4=local_asn.asn4())

        return {
            Attribute.CODE.ORIGIN: lambda: Origin.from_int(Origin.IGP),
            Attribute.CODE.AS_PATH: as_path,
            Attribute.CODE.LOCAL_PREF: lambda: LocalPreference.from_int(100) if internal or member else NOTHING,
        }

    def pack_attribute(
        self, negotiated: Negotiated, with_default: bool = True, without_next_hop: bool = False
    ) -> bytes:
        message = b''
        default = self._default_attributes(negotiated)
        # LOCAL_PREF is for our own AS and, in a confederation, its other members
        external = negotiated.local_as != negotiated.peer_as and not negotiated.confed_member
        # RFC 5065 5: no AS_CONFED_SEQUENCE or AS_CONFED_SET to a peer outside the confederation
        outside = negotiated.confed_outside

        # `without_next_hop` is asked for by the messages which carry their routes in an
        # MP_REACH_NLRI, where RFC 4760 section 3 says the attribute SHOULD NOT be sent.
        # It is a packing choice rather than a change to the collection: these attributes
        # are the RIB's, their index keys the attribute cache, and an IPv4 unicast route
        # sharing the set still needs its NEXT_HOP.
        skip: dict[int, Callable[[Attribute], bool]] = {
            Attribute.CODE.NEXT_HOP: lambda nh: without_next_hop or cast(NextHop, nh).ipv4() is not True,
            Attribute.CODE.LOCAL_PREF: lambda _: external,
        }

        keys = list(self)
        # `with_default` chooses whether the three defaults above are synthesised when they are
        # absent, not whether anything is encoded at all.  The brackets matter: a conditional
        # expression binds looser than `+`, so `keys + list(default) if with_default else []`
        # made the whole concatenation the true branch and `with_default=False` return b''.
        alls = set(keys + (list(default) if with_default else []))

        for code in sorted(alls):
            if code in AttributeCollection.INTERNAL:
                continue

            if code not in keys and code in default:
                attr = default[code]()
                if attr is not NOTHING:
                    # attr is Origin, AS2Path, or LocalPreference - all Attribute subclasses
                    message += attr.pack_attribute(negotiated)
                continue

            attribute = self[code]

            if code in skip and skip[code](attribute):
                continue

            if outside and isinstance(attribute, ASPath) and attribute.has_confed():
                attribute = attribute.without_confed()

            # RFC 4360 6, for a route we re-advertise only: an extended community the
            # operator configured non-transitive (link bandwidth) is meant for this peer.
            # RFC 5701 2 gives attribute 25 the same T bit, so it is stripped the same way.
            if code in EXTENDED_COMMUNITY_CODES and external and self.learned_from:
                transitive = cast(ExtendedCommunitiesBase, attribute).transitive_only()
                if transitive is None:
                    continue
                attribute = transitive

            message += attribute.pack_attribute(negotiated)

        return in_type_order(message)

    def json(self, include_nexthop: bool = False, generic: bool = False) -> str:
        # Cache only the default case (without nexthop and without generic) since that's most common
        if include_nexthop or generic:
            return ', '.join(self._generate_json(include_nexthop=include_nexthop, generic=generic))
        if not self._json:
            self._json = ', '.join(self._generate_json())
        return self._json

    def __repr__(self) -> str:
        if not self._str:
            self._str = ''.join(self._generate_text())
        return self._str

    def index(self) -> bytes:
        # Note: Using hash instead of string would save memory but risks collisions
        # since index() is used for equality comparisons. See lab/benchmark_attr_index.py
        if not self._idx:
            idx = ''.join(self._generate_text()) + ''.join(self[code].index_detail() for code in sorted(self.keys()))
            nexthop = str(self.get(Attribute.CODE.NEXT_HOP, 'missing'))
            text = '{} next-hop {}'.format(idx, nexthop) if nexthop else idx
            for code in self.INTERNAL_IDENTITY:
                if code in self:
                    text += ' internal-{:04x}'.format(code)
            self._idx = text.encode()
        return self._idx

    @classmethod
    def unpack(cls, data: Buffer, negotiated: Negotiated) -> AttributeCollection:
        # The cache belongs to the session, not to the process: what these bytes decode to
        # depends on what this session negotiated. Protocol builds one Negotiated per
        # session, so holding it here scopes the cache to the peer it was parsed for and
        # discards it when the session goes.
        if negotiated.attribute_cache is not None and data == negotiated.attribute_cache_packed:
            return negotiated.attribute_cache

        attributes = cls().parse(data, negotiated)
        attributes.learned_from = negotiated.peer_address

        if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in attributes:
            return attributes

        # RFC 6793 4.1: AS4_PATH and AS4_AGGREGATOR must not be carried between two NEW
        # speakers, and one which arrives anyway is discarded, the rest of the UPDATE
        # processed as it stands. Discard of the attribute, not treat-as-withdraw and not
        # a session reset. Merging it instead let a peer on a four octet session rewrite
        # the AS path we hold with bytes we are required to ignore.
        if negotiated.asn4:
            attributes.pop(Attribute.CODE.AS4_PATH, None)
            attributes.pop(Attribute.CODE.AS4_AGGREGATOR, None)
        else:
            attributes.reconcile_four_octet_as()

        # The UNSET sentinel is one process-wide object, not a session: a cache written
        # onto it would be shared by every caller, the exact bug this cache replaced.
        if not negotiated.attribute_cache_enabled:
            return attributes

        # MP_REACH and MP_UNREACH are popped off the collection downstream, so a cached one
        # would be served already emptied. Those are never cached, here as before.
        if Attribute.CODE.MP_REACH_NLRI not in attributes and Attribute.CODE.MP_UNREACH_NLRI not in attributes:
            negotiated.attribute_cache_packed = bytes(data)
            negotiated.attribute_cache = attributes
        else:
            negotiated.attribute_cache_packed = b''
            negotiated.attribute_cache = None

        return attributes

    @classmethod
    def from_attributes(cls, attrs: 'Attributes', negotiated: Negotiated) -> 'AttributeCollection':
        """Create AttributeCollection from wire Attributes for modification.

        This is the bridge from wire container to semantic container.

        Args:
            attrs: Wire-format Attributes container.
            negotiated: BGP session negotiated parameters.

        Returns:
            New AttributeCollection with parsed attributes.
        """
        return cls.unpack(attrs.packed, negotiated)

    @staticmethod
    def _dropped_on_receipt(negotiated: Negotiated) -> frozenset[int]:
        """The attributes this session removes from an UPDATE before decoding them.

        RFC 7606 7.5, 7.9 and 7.10: LOCAL_PREF, ORIGINATOR_ID and CLUSTER_LIST from an
        external neighbour are discarded, whatever their length, and the rest of the
        UPDATE is processed. RFC 9012 11: a filtered Tunnel Encapsulation attribute is
        "neither processed nor distributed", so it is not decoded either. Dropping the
        attribute, rather than adding a Discard marker, is what attribute discard means:
        the marker makes the reactor ignore the whole UPDATE.
        """
        dropped: set[int] = set()
        # an UPDATE we sent is decoded as written, it is not the peer's to filter
        if not negotiated.from_peer:
            return frozenset(dropped)
        if not negotiated.is_internal_neighbor:
            dropped.update(_INTERNAL_ONLY)
        if not negotiated.accepts_tunnel_encapsulation:
            dropped.add(Attribute.CODE.TUNNEL_ENCAP)
        return frozenset(dropped)

    def _malformation(self, aid: int | None, action: str, reason: str) -> None:
        """Record what a peer got wrong in one attribute, and apply the RFC 7606 action.

        The record is logged at debug here and as an error by the UPDATE, once, where the
        NLRI and the message are known (RFC 7606 6). RFC 6514 5 requires the same error for
        a malformed PMSI Tunnel attribute, which this covers.
        """
        assert action in (TREAT_AS_WITHDRAW_ACTION, ATTRIBUTE_DISCARD_ACTION), f'no RFC 7606 action {action}'
        code = -1 if aid is None else aid
        log.debug(
            lazymsg(
                'attribute.malformed name={name} aid=0x{aid:02X} action={action} reason="{reason}"',
                name=Attribute.CODE.names.get(code, 'unset'),
                aid=code & 0xFF,
                action=action,
                reason=reason,
            ),
            'parser',
        )
        self.malformed.append((code, action, reason))
        if action == TREAT_AS_WITHDRAW_ACTION:
            self.add(TreatAsWithdraw(aid))
            return
        self.add(Discard(aid))

    def _add_registered(
        self, aid: int, flag: int, kls: type[Attribute] | None, header: Buffer, value: Buffer, negotiated: Negotiated
    ) -> None:
        """Decode an attribute we have a class for, and apply RFC 7606 to what goes wrong."""
        # RFC 7606 7.3: a NEXT_HOP path attribute whose length is not four, zero included,
        # is malformed. The rule is applied here, where attribute 3 is known to be what is
        # being read, because NextHop also decodes the next hop inside MP_REACH_NLRI, which
        # RFC 4760 lets the family size: sixteen octets for IPv6. Sharing one length rule
        # accepted a sixteen octet attribute 3. Not withdrawn here: see next_hop_malformed.
        if aid == Attribute.CODE.NEXT_HOP and len(value) != NextHop.ATTRIBUTE_SIZE_BYTES:
            self.next_hop_malformed = f'a length of {len(value)}'
            return

        # An empty MP attribute is one more length below its minimum, so it goes on to its
        # decoder, which answers it with the 3/9 of RFC 7606 5.3 as it does four octets.
        if len(value) == 0 and kls and not kls.VALID_ZERO and aid not in _MP_CODES:
            # A zero length is one more wrong length, so an attribute whose RFC 7606 rule
            # is attribute discard (AGGREGATOR, 7.7) is discarded rather than withdrawn.
            # Withdrawing was harmless while treat-as-withdraw with no NLRI did nothing;
            # RFC 7606 5.2 now makes it a session reset.
            if kls.DISCARD and not kls.TREAT_AS_WITHDRAW:
                self._malformation(aid, ATTRIBUTE_DISCARD_ACTION, 'a length of zero')
                return
            self._malformation(aid, TREAT_AS_WITHDRAW_ACTION, 'a length of zero')
            return

        try:
            decoded: Attribute = Attribute.unpack(aid, flag, value, negotiated)
        except (IndexError, ValueError) as exc:
            if kls and kls.TREAT_AS_WITHDRAW:
                self._malformation(aid, TREAT_AS_WITHDRAW_ACTION, str(exc))
                return
            # DISCARD was honoured for Notify below but not here, so an attribute
            # RFC 7606 says to drop escaped as a raw ValueError instead: AGGREGATOR
            # at any length but 0 or 6 came out of Update.unpack_message untyped,
            # where the reactor's catch-all turned RFC 7606 7.7 attribute discard
            # into a session reset
            if kls and kls.DISCARD:
                self._malformation(aid, ATTRIBUTE_DISCARD_ACTION, str(exc))
                return
            raise exc
        except TreatAsWithdrawNotify as exc:
            # the decoder named the RFC 7606 action itself, see TreatAsWithdrawNotify
            self._malformation(aid, TREAT_AS_WITHDRAW_ACTION, exc.detail)
            return
        except Notify as exc:
            if kls and kls.TREAT_AS_WITHDRAW:
                self._malformation(aid, TREAT_AS_WITHDRAW_ACTION, exc.detail)
                return
            if kls and kls.DISCARD:
                self._malformation(aid, ATTRIBUTE_DISCARD_ACTION, exc.detail)
                return
            raise _with_the_attribute(exc, header, value) from None

        self.add(decoded)

    def _add_flag_conflict(self, aid: int, flag: int, kls: type[Attribute] | None, attribute: Buffer) -> None:
        """A known attribute whose flags are not the ones its RFC gives it (RFC 7606 3 (c))."""
        name = Attribute.CODE.name(aid)
        # RFC 7606 5.3 lists "the attribute flags of the attribute are inconsistent
        # with those specified in [RFC4760]" as one of the ways an MP_REACH_NLRI or
        # MP_UNREACH_NLRI is incorrect, and 3 (j) says that when the MP attributes
        # cannot be successfully parsed the session reset approach MUST be followed.
        # Treat-as-withdraw is not available here: the NLRI are inside the attribute
        # the flags stopped us recognising, so there is nothing left to withdraw and
        # dropping the attribute makes the routes it carried vanish in silence.
        if aid in _MP_CODES:
            reason = f'has the invalid flag 0x{flag:02X}, RFC 4760 makes it optional non-transitive'
            raise _unframed_mp_attribute(aid, reason, attribute)
        reason = f'the invalid flag 0x{flag:02X}'
        if aid == Attribute.CODE.NEXT_HOP:
            # treat-as-withdraw or ignored, which the UPDATE decides: see next_hop_malformed
            self.next_hop_malformed = reason
            return
        if kls and kls.TREAT_AS_WITHDRAW:
            self._malformation(aid, TREAT_AS_WITHDRAW_ACTION, reason)
            return
        if kls and kls.DISCARD:
            # Discarded without a marker, as it always was: the attribute is not kept
            self.malformed.append((aid, ATTRIBUTE_DISCARD_ACTION, reason))
            return
        # Attributes in neither TREAT_AS_WITHDRAW nor DISCARD are an implementation gap:
        # if this fires, give the class one of the two
        log.debug(lazymsg('attribute.flag.unspecified name={name} flag=0x{flag:02X}', name=name, flag=flag), 'parser')

    def _add_unknown(self, aid: int, flag: int, attribute: Buffer) -> None:
        """An attribute we have no class for: a transitive one is passed on, the rest ignored."""
        if not flag & Attribute.Flag.TRANSITIVE:
            log.debug(
                lazymsg('attribute.unknown type=non-transitive flag=0x{flag:02X} aid=0x{aid:02X}', flag=flag, aid=aid),
                'parser',
            )
            return
        log.debug(
            lazymsg('attribute.unknown type=transitive flag=0x{flag:02X} aid=0x{aid:02X}', flag=flag, aid=aid),
            'parser',
        )
        try:
            decoded_generic: Attribute = GenericAttribute.make_generic(aid, flag | Attribute.Flag.PARTIAL, attribute)
        except IndexError as exc:
            self._malformation(aid, TREAT_AS_WITHDRAW_ACTION, str(exc))
            return
        self.add(decoded_generic, attribute)

    def _framed(self, data: Buffer) -> tuple[int, int, int, int] | None:
        """The flag, type, header size and length of the attribute `data` starts with.

        None when the header is cut short, which RFC 7606 4 makes treat-as-withdraw for the
        whole UPDATE (recorded here), and 3 (j) a session reset for an MP attribute.
        """
        if len(data) < 2:
            # not even a type: there is no attribute to name, and no MP attribute to reset for
            self._malformation(None, TREAT_AS_WITHDRAW_ACTION, f'a truncated attribute header of {len(data)} octets')
            return None
        aid = data[1]
        offset = 4 if data[0] & Attribute.Flag.EXTENDED_LENGTH else 3
        if len(data) < offset:
            if aid in _MP_CODES:
                raise _unframed_mp_attribute(aid, 'has a truncated header', data)
            self._malformation(aid, TREAT_AS_WITHDRAW_ACTION, f'a truncated attribute header of {len(data)} octets')
            return None
        length = data[2] if offset == 3 else (data[2] << 8) + data[3]
        # RFC 7606 section 4: an Attribute Length past the end of the section is an error
        # in the message framing, not in one attribute, so the whole UPDATE is withdrawn.
        # Slicing does not raise on an overrun, so without this the attribute was decoded
        # from however many bytes happened to remain and accepted as though well formed.
        if length > len(data) - offset:
            if aid in _MP_CODES:
                raise _unframed_mp_attribute(aid, f'claims {length} octets where {len(data) - offset} remain', data)
            self._malformation(aid, TREAT_AS_WITHDRAW_ACTION, f'a length of {length} past the end of the attributes')
            return None
        return data[0], aid, offset, length

    def _is_repeated(self, aid: int, flag: int, kls: type[Attribute] | None, seen: set[int]) -> bool:
        """RFC 7606 3 (g): a second MP attribute resets, any other second copy is skipped."""
        if aid not in seen and aid not in self:
            seen.add(aid)
            return False
        if kls and kls.NO_DUPLICATE:
            raise Notify(3, 1, 'multiple attribute for {}'.format(Attribute.CODE.name(aid)))
        log.debug(
            lazymsg(
                'attribute.duplicate name={name} flag=0x{flag:02X} aid=0x{aid:02X} action=skip',
                name=Attribute.CODE.names.get(aid, 'unset'),
                flag=flag,
                aid=aid,
            ),
            'parser',
        )
        return True

    # Iterative, not recursive: every branch used to end `return self.parse(left, negotiated)`,
    # costing one stack frame per attribute on peer-controlled input (see
    # tests/unit/test_attribute_parse_iterative.py for the measured RecursionError crossover).
    # The `while data:` loop is bounded: each iteration either returns, or consumes a whole
    # header and value (`_framed` checked both are there), so `data` strictly shrinks and the
    # loop runs at most `len(data) // 3` times; `data` is itself bounded by the negotiated
    # message size checked upstream in Update.unpack_message.
    def parse(self, data: Buffer, negotiated: Negotiated) -> AttributeCollection:
        dropped = self._dropped_on_receipt(negotiated)
        # RFC 7606 3 (g) keeps the first occurrence on the wire, decodable or not. A malformed
        # first copy is stored as Discard or TreatAsWithdraw under their own codes, so asking
        # the collection whether it holds the code let a second copy in as the first.
        seen: set[int] = set()
        while data:
            framed = self._framed(data)
            if framed is None:
                return self
            flag, aid, offset, length = framed
            header = data[:offset]
            attribute = data[offset : offset + length]
            data = data[offset + length :]

            log.debug(lazyattribute(flag, aid, length, attribute), 'parser')

            # The Partial bit is removed before the flags are compared, for every attribute.
            # RFC 4271 4.3 has the sender clear it on well-known and optional non-transitive
            # attributes, but RFC 7606 3 (c) makes only an Optional or Transitive bit in
            # conflict a malformation: an ORIGIN with Partial set was treated as withdraw.
            # What we send carries the bit our classes give it, so it is not repeated.
            flag = flag & Attribute.Flag.MASK_PARTIAL & 0xFF

            if aid in dropped:
                log.debug(
                    lazymsg(
                        'attribute.filtered name={name} aid=0x{aid:02X} peer={peer} action=discard',
                        name=Attribute.CODE.names.get(aid, 'unset'),
                        aid=aid,
                        peer='internal' if negotiated.is_internal_neighbor else 'external',
                    ),
                    'parser',
                )
                continue

            # Get the attribute class to check its behavior flags
            kls = Attribute.klass_by_id(aid)
            if self._is_repeated(aid, flag, kls, seen):
                continue

            if Attribute.registered(aid, flag):
                self._add_registered(aid, flag, kls, header, attribute, negotiated)
            elif aid in Attribute.attributes_known:
                self._add_flag_conflict(aid, flag, kls, bytes(header) + bytes(attribute))
            else:
                self._add_unknown(aid, flag, attribute)

        return self

    def reconcile_four_octet_as(self) -> None:
        """RFC 6793 4.2.3: settle the AS4_ attributes an OLD speaker sent beside the real ones.

        The aggregator bullets come first because the AGGREGATOR decides whether the AS4_PATH
        is looked at at all, and only then is the path reconstructed.
        """
        aggregator = self.get(Attribute.CODE.AGGREGATOR, None)
        aggregator4 = self.get(Attribute.CODE.AS4_AGGREGATOR, None)

        if aggregator is not None and aggregator4 is not None:
            assert isinstance(aggregator, Aggregator), 'the AGGREGATOR did not decode to an Aggregator'
            if aggregator.asn != AS_TRANS:
                # An aggregating AS which is a real number was not written by a speaker
                # translating a four-octet one, so both AS4_ attributes are noise: the
                # AGGREGATOR is the aggregating node and the AS_PATH is the path.
                self.pop(Attribute.CODE.AS4_AGGREGATOR, None)
                self.pop(Attribute.CODE.AS4_PATH, None)
                return
            # AS_TRANS is a placeholder, not an Autonomous System. Leaving the AGGREGATOR in
            # told a consumer of the JSON that AS 23456 aggregated the route; the
            # AS4_AGGREGATOR beside it holds the AS number which did.
            self.pop(Attribute.CODE.AGGREGATOR, None)

        if Attribute.CODE.AS_PATH in self and Attribute.CODE.AS4_PATH in self:
            self.merge_attributes()

    @staticmethod
    def _as_number_count(segments: tuple[PathSegment, ...]) -> int:
        """How many AS numbers a path holds, by the rule of RFC 4271 section 9.1.2.2.

        An AS_SET counts as one whatever it holds, and a confederation segment counts as
        none (RFC 5065 section 5.3). RFC 6793 4.2.3 names this count twice, so the
        reconstruction below has to use it rather than a flat count of members.
        """
        total = 0
        for segment in segments:
            if isinstance(segment, SEQUENCE):
                total += len(segment)
            elif isinstance(segment, SET):
                total += 1
        return total

    @classmethod
    def _leading_as_numbers(cls, segments: tuple[PathSegment, ...], wanted: int) -> list[PathSegment]:
        """The leading part of a path holding `wanted` AS numbers, cutting a segment if it must.

        RFC 6793 4.2.3 takes "as many AS numbers and path segments as necessary from the
        leading part of the AS_PATH", so a sequence which overshoots is cut rather than
        dropped whole, and a confederation segment comes along without paying for itself.

        It comes along whenever it leads the path or follows a prepended segment, even once
        no AS number is wanted any more (the same paragraph, "SHALL be prepended"). Stopping
        at the count dropped the AS_CONFED_SEQUENCE of a route from a two octet member of
        our confederation, which was then read as having come from outside it.
        """
        assert wanted >= 0, 'the AS4_PATH is never longer than the AS_PATH here'
        leading: list[PathSegment] = []
        for segment in segments:
            if segment.ID in (CONFED_SEQUENCE.ID, CONFED_SET.ID):
                leading.append(segment)
                continue
            if wanted <= 0:
                break
            if isinstance(segment, SEQUENCE) and len(segment) > wanted:
                leading.append(SEQUENCE(segment[:wanted]))
                break
            leading.append(segment)
            wanted -= cls._as_number_count((segment,))
        return leading

    @staticmethod
    def _coalesce_segments(segments: list[PathSegment]) -> list[PathSegment]:
        """Join neighbouring sequences, so the join shows as one segment rather than a seam.

        Only sequences: two adjacent AS_SETs count as two AS numbers and one holding both
        members counts as one, so merging those would change the length of the path.
        """
        joined: list[PathSegment] = []
        for segment in segments:
            previous = joined[-1] if joined else None
            if isinstance(segment, SEQUENCE) and isinstance(previous, SEQUENCE):
                joined[-1] = SEQUENCE(list(previous) + list(segment))
                continue
            if isinstance(segment, CONFED_SEQUENCE) and isinstance(previous, CONFED_SEQUENCE):
                joined[-1] = CONFED_SEQUENCE(list(previous) + list(segment))
                continue
            joined.append(segment)
        return joined

    @classmethod
    def _reconstruct_as_path(cls, as2path: AS2Path, as4path: AS2Path) -> list[PathSegment]:
        """RFC 6793 4.2.3, which obsoletes the RFC 4893 this used to cite.  Two rules.

        When the AS_PATH holds fewer AS numbers than the AS4_PATH the AS4_PATH is ignored and
        the AS_PATH is the answer.  Otherwise the leading part of the AS_PATH is prepended to
        the AS4_PATH so the result holds as many AS numbers as the AS_PATH did.

        This used to work one segment kind at a time, taking sequences from sequences and sets
        from sets.  An AS4_PATH whose only segment was a set was therefore matched against an
        AS_PATH which had no set, contributed nothing, and left in place the AS_TRANS it had
        been sent to replace: exabgp published 23456 as a transit AS, which is the one outcome
        the whole mechanism exists to avoid.  Counting over the whole path by RFC 4271 9.1.2.2
        and prepending across segment kinds is what the sentence actually asks for.
        """
        segments2 = as2path.aspath
        segments4 = as4path.aspath
        count2 = cls._as_number_count(segments2)
        count4 = cls._as_number_count(segments4)

        if count2 < count4:
            return list(segments2)

        return cls._coalesce_segments(cls._leading_as_numbers(segments2, count2 - count4) + list(segments4))

    def merge_attributes(self) -> None:
        as2path_attr = self[Attribute.CODE.AS_PATH]
        as4path_attr = self[Attribute.CODE.AS4_PATH]
        self.remove(Attribute.CODE.AS_PATH)
        self.remove(Attribute.CODE.AS4_PATH)

        # Type narrowing - these are guaranteed to be AS2Path after parsing
        assert isinstance(as2path_attr, AS2Path), f'AS_PATH must be AS2Path, got {type(as2path_attr)}'
        assert isinstance(as4path_attr, AS2Path), f'AS4_PATH must be AS2Path, got {type(as4path_attr)}'
        as2path: AS2Path = as2path_attr
        as4path: AS2Path = as4path_attr

        # this key is unique as index length is a two header, plus a number of ASN of size 2 or 4
        # so adding the: make the length odd and unique
        key = bytes(as2path.index) + b':' + bytes(as4path.index)

        # found a cache copy
        cache_dict = Attribute.cache.get(Attribute.CODE.AS_PATH)
        cached = cache_dict.get(key, None) if cache_dict else None
        if cached:
            self.add(cached, key)
            return

        # Reconstruction recovers four-octet ASNs even on a two-octet wire session.
        aspath = AS2Path.make_aspath(self._reconstruct_as_path(as2path, as4path), asn4=True)
        self.add(aspath, key)

    def __hash__(self) -> int:
        # Use index() which includes nexthop, unlike repr() which excludes it
        return hash(self.index())

    def __eq__(self, other: object) -> bool:
        return self.sameValuesAs(other)

    # written out: mypyc fails to derive __ne__ from __eq__ for the subclasses. The operator,
    # not a call to __eq__, so NotImplemented is answered the way Python answers it.
    def __ne__(self, other: object) -> bool:
        return not self == other

    # BaGPipe code ..

    # test that sets of attributes exactly match
    # can't rely on __eq__ for this, because __eq__ relies on Attribute.__eq__ which does not look at attributes values

    def sameValuesAs(self, other: object) -> bool:
        if not isinstance(other, AttributeCollection):
            return False

        try:
            for key in set(self.keys()).union(set(other.keys())):
                if key == Attribute.CODE.MP_REACH_NLRI or key == Attribute.CODE.MP_UNREACH_NLRI:
                    continue

                sval = self[key]
                oval = other[key]

                # In the case where the attribute is Communities or
                # extended communities, we want to compare values independently of their order
                if isinstance(sval, Communities):
                    if not isinstance(oval, Communities):
                        return False
                    # Compare sorted community lists by their packed bytes
                    if sorted(bytes(c._packed) for c in sval.communities) != sorted(
                        bytes(c._packed) for c in oval.communities
                    ):
                        return False
                elif sval != oval:
                    return False
            return True
        except KeyError:
            return False


# ======================================================================= Attributes (Wire)
#
# Wire-format path attributes container (bytes-first pattern).
# This class stores the raw packed bytes as the canonical representation.
# Parsing to semantic objects (AttributeCollection) is lazy.


class Attributes:
    """Wire-format path attributes container (bytes-first).

    Stores raw packed path attributes bytes as the canonical representation.
    Provides lazy parsing to semantic AttributeCollection when needed.

    This follows the "packed-bytes-first" pattern used by individual
    Attribute classes - the wire format is stored directly, and semantic
    values are derived via properties.
    """

    def __init__(self, packed: Buffer, context: 'Negotiated | None' = None) -> None:
        """Create Attributes from packed bytes.

        Args:
            packed: Raw path attributes bytes (concatenated TLV attributes).
            context: Optional negotiated context for parsing.
        """
        self._packed = packed
        self._context = context

    @classmethod
    def from_set(cls, attr_set: AttributeCollection, negotiated: 'Negotiated') -> 'Attributes':
        """Create Attributes from semantic AttributeCollection.

        Args:
            attr_set: Semantic attributes container.
            negotiated: BGP session negotiated parameters.

        Returns:
            New Attributes with packed bytes.
        """
        packed = attr_set.pack_attribute(negotiated)
        return cls(packed, negotiated)

    @property
    def packed(self) -> Buffer:
        """Raw packed path attributes bytes."""
        return self._packed

    def unpack_attributes(self, negotiated: 'Negotiated | None' = None) -> AttributeCollection:
        """Unpack to semantic AttributeCollection.

        Args:
            negotiated: BGP session negotiated parameters.
                       If not provided, uses stored context.

        Returns:
            Unpacked AttributeCollection (semantic container).
        """
        ctx = negotiated or self._context
        if ctx is None:
            raise RuntimeError('Attributes.unpack_attributes() requires negotiated context')
        return AttributeCollection.unpack(self._packed, ctx)

    def __getitem__(self, code: int) -> Attribute:
        """Get attribute by code."""
        for attr in self:
            if attr.ID == code:
                return attr
        raise KeyError(code)

    def has(self, code: int) -> bool:
        """Check if attribute exists."""
        for attr in self:
            if attr.ID == code:
                return True
        return False

    def __contains__(self, code: object) -> bool:
        """Check if attribute with given code exists (enables 'in' operator)."""
        if not isinstance(code, int):
            return False
        return self.has(code)

    def __iter__(self) -> Iterator[Attribute]:
        """Iterate over Attribute objects with buffer slices.

        Yields Attribute instances that store slices of self._packed.
        Each attribute parses its value lazily via properties - no upfront
        parsing cost.

        Yields:
            Attribute instances (MED, LocalPreference, Origin, etc.)
            Each stores a memoryview/slice of the buffer for lazy parsing.

        Note:
            Requires self._context to be set. If not set, raises RuntimeError.
            Invalid attributes are skipped (logged but not yielded).
            A header or value running past the end of the bytes raises Notify 3/1.
        """
        if self._context is None:
            raise RuntimeError('Attributes.__iter__() requires negotiated context')

        data: Buffer = self._packed
        # bounded: every pass consumes at least a three byte header, or raises
        while data:
            if len(data) < 3:
                raise Notify.short(3, 1, 'path attribute header', 3, len(data))
            flag = data[0]
            code = data[1]

            offset = 4 if flag & Attribute.Flag.EXTENDED_LENGTH else 3
            if len(data) < offset:
                raise Notify.short(3, 1, 'extended length path attribute header', offset, len(data))
            length = unpack('!H', data[2:4])[0] if offset == 4 else data[2]
            if len(data) < offset + length:
                raise Notify.short(3, 1, f'path attribute {code}', offset + length, len(data))

            # Pass buffer slice to attribute - it stores and parses lazily
            value_slice = data[offset : offset + length]

            try:
                # Attribute.unpack creates instance with buffer slice
                # Properties parse dynamically when accessed
                attr = Attribute.unpack(code, flag, value_slice, self._context)
                if attr is not None:
                    yield attr
            except (Notify, ValueError) as exc:
                # This iterator is a read-only view over bytes already accepted, so it has
                # no session to close and skipping is the only thing it can do. It says so
                # rather than saying nothing: a malformed attribute vanishing without a word
                # is how a route ends up different from what the peer sent, with nothing
                # anywhere to trace it back to.
                log.debug(
                    lazymsg('attributes.wire.skipped code={code} error={error}', code=code, error=str(exc)),
                    'parser',
                )

            data = data[offset + length :]

    def to_collection(self) -> AttributeCollection:
        """Convert to AttributeCollection for modification.

        Creates a semantic container from wire bytes. Use this when you
        need to add/remove/modify attributes.

        Returns:
            AttributeCollection with parsed attributes.

        Note:
            Requires self._context to be set.
        """
        return self.unpack_attributes()


# Backward compatibility aliases
AttributesWire = Attributes  # Old wire container name
AttributeSet = AttributeCollection  # Old semantic container name
