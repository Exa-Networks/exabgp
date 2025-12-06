"""attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from struct import unpack
from typing import TYPE_CHECKING, Any, ClassVar, Generator, cast

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.aspath import SEQUENCE, SET, AS2Path
from exabgp.bgp.message.update.attribute.attribute import Attribute, Discard, TreatAsWithdraw
from exabgp.bgp.message.update.attribute.watchdog import Watchdog, NoWatchdog

# For bagpipe
from exabgp.bgp.message.update.attribute.community import Communities
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunitiesBase
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.logger import lazyattribute, lazymsg, log


class _NOTHING:
    def pack(self, _: Any = None) -> bytes:
        return b''

    def pack_attribute(self, _: Any = None) -> bytes:
        return b''


NOTHING: _NOTHING = _NOTHING()


# =================================================================== AttributeCollection
#
# Semantic container for BGP path attributes.
# Stores parsed Attribute objects in a dict-like structure.

# 0                   1
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  Attr. Flags  |Attr. Type Code|
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class AttributeCollection(dict):
    # Internal pseudo-attributes (no dedicated classes exist for these)
    INTERNAL: ClassVar[tuple[int, ...]] = (
        Attribute.CODE.INTERNAL_SPLIT,
        Attribute.CODE.INTERNAL_WATCHDOG,
        Attribute.CODE.INTERNAL_NAME,
        Attribute.CODE.INTERNAL_WITHDRAW,
    )

    # The previously parsed AttributeCollection
    cached: ClassVar[AttributeCollection | None] = None
    # previously parsed attribute, from which cached was made of
    previous: ClassVar[bytes] = b''

    representation: ClassVar[dict[int, tuple[str, str, str | tuple[str, ...], str, str]]] = {
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
        Attribute.CODE.PMSI_TUNNEL: ('string', '', 'pmsi', '%s', '%s'),
        Attribute.CODE.AIGP: ('integer', '', 'aigp', '%s', '%s'),
        Attribute.CODE.BGP_LS: ('list', '', 'bgp-ls', '%s', '%s'),
        Attribute.CODE.BGP_PREFIX_SID: ('list', '', 'bgp-prefix-sid', '%s', '%s'),
        Attribute.CODE.INTERNAL_NAME: ('string', '', 'name', '%s', '%s'),
        Attribute.CODE.INTERNAL_DISCARD: ('string', '', 'error', '%s', '%s'),
        Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW: ('string', '', 'error', '%s', '%s'),
    }

    _str: str
    _idx: str
    _json: str
    cacheable: bool

    def _generate_text(self) -> Generator[str, None, None]:
        for code in sorted(self.keys()):
            # Skip internal pseudo-attributes
            if code in AttributeCollection.INTERNAL:
                continue

            attribute = self[code]

            # Skip attributes marked as NO_GENERATION
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
                yield ' {} {}'.format(name, presentation % str(attribute))
            elif how == 'multiple':
                yield ' {} {}'.format(name[0], presentation % str(attribute))
            else:
                yield ' {} {}'.format(name, presentation % str(attribute))

    def _generate_json(self) -> Generator[str, None, None]:
        for code in sorted(self.keys()):
            # Skip internal pseudo-attributes
            if code in AttributeCollection.INTERNAL:
                continue

            attribute = self[code]

            # Skip attributes marked as NO_GENERATION (next-hop is defined with the NLRI)
            if attribute.NO_GENERATION:
                continue

            if code not in self.representation:
                yield '"attribute-0x{:02X}-0x{:02X}": "{}"'.format(code, attribute.FLAG, str(attribute))
                continue

            how, _, name, _, presentation = self.representation[code]
            if how == 'boolean':
                yield '"{}": {}'.format(name, 'true' if self.has(code) else 'false')
            elif how == 'string':
                yield '"{}": "{}"'.format(name, presentation % str(attribute))
            elif how == 'list':
                yield '"{}": {}'.format(name, presentation % attribute.json())
            elif how == 'multiple':
                for n in name:
                    value = attribute.json(n)
                    if value:
                        yield '"{}": {}'.format(n, presentation % value)
            elif how == 'inet':
                yield '"{}": "{}"'.format(name, presentation % str(attribute))
            # Should never be ran
            else:
                yield '"{}": {}'.format(name, presentation % str(attribute))

    def __init__(self) -> None:
        dict.__init__(self)
        # cached representation of the object
        self._str = ''
        self._idx = ''
        self._json = ''
        # The parsed attributes have no mp routes and/or those are last
        self.cacheable = True
        # Note: Attribute.caching is set in application/server.py at startup

    def has(self, k: int) -> bool:
        return k in self

    def add(self, attribute: Attribute | TreatAsWithdraw | Discard | None, _: Any = None) -> None:
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
            for community in attribute.communities:
                self[attribute.ID].add(community)
            return

        self._str = ''
        self._json = ''
        self[attribute.ID] = attribute

    def remove(self, attrid: int) -> None:
        self.pop(attrid)

    def watchdog(self) -> Watchdog:
        value = self.pop(Attribute.CODE.INTERNAL_WATCHDOG, None)
        if value is None:
            return NoWatchdog
        return Watchdog(str(value))

    def withdraw(self) -> bool:
        return self.pop(Attribute.CODE.INTERNAL_WITHDRAW, None) is not None

    def pack_attribute(self, negotiated: Negotiated, with_default: bool = True) -> bytes:
        local_asn = negotiated.local_as
        peer_asn = negotiated.peer_as

        message = b''

        default = {
            Attribute.CODE.ORIGIN: lambda left, right: Origin.from_int(Origin.IGP),
            Attribute.CODE.AS_PATH: lambda left, right: (
                AS2Path.make_aspath([])
                if left == right
                else AS2Path.make_aspath(
                    [
                        SEQUENCE(
                            [
                                local_asn,
                            ],
                        ),
                    ],
                )
            ),
            Attribute.CODE.LOCAL_PREF: lambda left, right: LocalPreference.from_int(100) if left == right else NOTHING,
        }

        skip = {
            Attribute.CODE.NEXT_HOP: lambda left, right, nh: nh.ipv4() is not True,
            Attribute.CODE.LOCAL_PREF: lambda left, right, nh: left != right,
        }

        keys = list(self)
        alls = set(keys + list(default) if with_default else [])

        for code in sorted(alls):
            if code in AttributeCollection.INTERNAL:
                continue

            if code not in keys and code in default:
                attr = default[code](local_asn, peer_asn)
                if attr is not NOTHING:
                    # attr is Origin, AS2Path, or LocalPreference - all Attribute subclasses
                    message += attr.pack_attribute(negotiated)
                continue

            attribute = self[code]

            if code in skip and skip[code](local_asn, peer_asn, attribute):
                continue

            message += attribute.pack_attribute(negotiated)

        return message

    def json(self) -> str:
        if not self._json:
            self._json = ', '.join(self._generate_json())
        return self._json

    def __repr__(self) -> str:
        if not self._str:
            self._str = ''.join(self._generate_text())
        return self._str

    def index(self) -> str:
        # Note: Using hash instead of string would save memory but risks collisions
        # since index() is used for equality comparisons. See lab/benchmark_attr_index.py
        if not self._idx:
            idx = ''.join(self._generate_text())
            nexthop = str(self.get(Attribute.CODE.NEXT_HOP, 'missing'))
            self._idx = '{} next-hop {}'.format(idx, nexthop) if nexthop else idx
        return self._idx

    @classmethod
    def unpack(cls, data: Buffer, negotiated: Negotiated) -> AttributeCollection:
        if cls.cached and data == cls.previous:
            return cls.cached

        attributes = cls().parse(data, negotiated)

        if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in attributes:
            return attributes

        if Attribute.CODE.AS_PATH in attributes and Attribute.CODE.AS4_PATH in attributes:
            attributes.merge_attributes()

        if Attribute.CODE.MP_REACH_NLRI not in attributes and Attribute.CODE.MP_UNREACH_NLRI not in attributes:
            cls.previous = data
            cls.cached = attributes
        else:
            cls.previous = b''
            cls.cached = None

        return attributes

    @staticmethod
    def flag_attribute_content(data: Buffer) -> tuple[int, int, bytes]:
        flag = Attribute.Flag(data[0])
        attr = data[1]

        if flag & Attribute.Flag.EXTENDED_LENGTH:
            length = unpack('!H', data[2:4])[0]
            return flag, attr, data[4 : length + 4]
        length = data[2]
        return flag, attr, data[3 : length + 3]

    def parse(self, data: bytes, negotiated: Negotiated) -> AttributeCollection:
        if not data:
            return self

        try:
            # We do not care if the attribute are transitive or not as we do not redistribute
            flag = Attribute.Flag(data[0])
            aid = data[1]
        except IndexError:
            self.add(TreatAsWithdraw())
            return self

        try:
            offset = 3
            length = data[2]

            if flag & Attribute.Flag.EXTENDED_LENGTH:
                offset = 4
                length = (length << 8) + data[3]
        except IndexError:
            self.add(TreatAsWithdraw(aid))
            return self

        data = data[offset:]
        left = data[length:]
        attribute = data[:length]

        log.debug(lazyattribute(flag, aid, length, data[:length]), 'parser')

        # remove the PARTIAL bit before comparaison if the attribute is optional
        if aid in Attribute.attributes_optional:
            flag = Attribute.Flag(flag & Attribute.Flag.MASK_PARTIAL & 0xFF)
            # flag &= ~Attribute.Flag.PARTIAL & 0xFF  # cleaner than above (python use signed integer for ~)

        # Get the attribute class to check its behavior flags
        kls = Attribute.klass_by_id(aid)

        if aid in self:
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
            return self.parse(left, negotiated)

        # handle the attribute if we know it
        if Attribute.registered(aid, flag):
            if length == 0 and kls and not kls.VALID_ZERO:
                self.add(TreatAsWithdraw(aid))
                return self.parse(left, negotiated)

            try:
                decoded: Attribute = Attribute.unpack(aid, flag, attribute, negotiated)
            except (IndexError, ValueError) as exc:
                if kls and kls.TREAT_AS_WITHDRAW:
                    self.add(TreatAsWithdraw(aid))
                    return self.parse(left, negotiated)
                raise exc
            except Notify as exc:
                if kls and kls.TREAT_AS_WITHDRAW:
                    self.add(TreatAsWithdraw())
                    return self.parse(left, negotiated)
                if kls and kls.DISCARD:
                    self.add(Discard())
                    return self.parse(left, negotiated)
                raise exc

            self.add(decoded)
            return self.parse(left, negotiated)

        # Note: Unknown attributes are handled below via GenericAttribute for transitive
        # attributes, or logged/discarded for others. This differs from capability's
        # registered fallback pattern but achieves the same goal.

        # if we know the attribute but the flag is not what the RFC says.
        if aid in Attribute.attributes_known:
            if kls and kls.TREAT_AS_WITHDRAW:
                log.debug(
                    lambda: 'invalid flag for attribute {} (flag 0x{:02X}, aid 0x{:02X}) treat as withdraw'.format(
                        Attribute.CODE.names.get(aid, 'unset'), flag, aid
                    ),
                    'parser',
                )
                self.add(TreatAsWithdraw())
            if kls and kls.DISCARD:
                log.debug(
                    lambda: 'invalid flag for attribute {} (flag 0x{:02X}, aid 0x{:02X}) discard'.format(
                        Attribute.CODE.names.get(aid, 'unset'), flag, aid
                    ),
                    'parser',
                )
                return self.parse(left, negotiated)
            # Attributes not in TREAT_AS_WITHDRAW or DISCARD fall through to this log
            # This catches implementation gaps - if this fires, add aid to one of the lists
            log.debug(
                lambda: 'invalid flag for attribute {} (flag 0x{:02X}, aid 0x{:02X}) unspecified (should not happen)'.format(
                    Attribute.CODE.names.get(aid, 'unset'), flag, aid
                ),
                'parser',
            )
            return self.parse(left, negotiated)

        # it is an unknown transitive attribute we need to pass on
        if flag & Attribute.Flag.TRANSITIVE:
            log.debug(
                lazymsg('attribute.unknown type=transitive flag=0x{flag:02X} aid=0x{aid:02X}', flag=flag, aid=aid),
                'parser',
            )
            try:
                decoded_generic: Attribute = GenericAttribute.make_generic(
                    aid, flag | Attribute.Flag.PARTIAL, attribute
                )
            except IndexError:
                self.add(TreatAsWithdraw(aid), attribute)
                return self.parse(left, negotiated)
            self.add(decoded_generic, attribute)
            return self.parse(left, negotiated)

        # it is an unknown non-transitive attribute we can ignore.
        log.debug(
            lambda: 'ignoring unknown non-transitive attribute (flag 0x{:02X}, aid 0x{:02X})'.format(flag, aid),
            'parser',
        )
        return self.parse(left, negotiated)

    def merge_attributes(self) -> None:
        as2path = self[Attribute.CODE.AS_PATH]
        as4path = self[Attribute.CODE.AS4_PATH]
        self.remove(Attribute.CODE.AS_PATH)
        self.remove(Attribute.CODE.AS4_PATH)

        # this key is unique as index length is a two header, plus a number of ASN of size 2 or 4
        # so adding the: make the length odd and unique
        key = '{}:{}'.format(as2path.index, as4path.index)

        # found a cache copy
        cached = Attribute.cache.get(Attribute.CODE.AS_PATH, {}).get(key, None)
        if cached:
            self.add(cached, key)
            return

        # as_seq = []
        # as_set = []

        len2 = len(as2path.as_seq)
        len4 = len(as4path.as_seq)

        # RFC 4893 section 4.2.3
        if len2 < len4:
            as_seq = as2path.as_seq
        else:
            as_seq = as2path.as_seq[:-len4]
            as_seq.extend(as4path.as_seq)

        len2 = len(as2path.as_set)
        len4 = len(as4path.as_set)

        if len2 < len4:
            as_set = as4path.as_set
        else:
            as_set = as2path.as_set[:-len4]
            as_set.extend(as4path.as_set)

        # Build segments from merged ASN lists
        segments: list[SET | SEQUENCE] = []
        if as_seq:
            segments.append(SEQUENCE(as_seq))
        if as_set:
            segments.append(SET(as_set))
        aspath = AS2Path.make_aspath(segments)
        self.add(aspath, key)

    def __hash__(self) -> int:
        # FIXME: two routes with distinct nh but other attributes equal
        # will hash to the same value until repr represents the nh (??)
        return hash(repr(self))

    def __eq__(self, other: object) -> bool:
        return self.sameValuesAs(other)

    # BaGPipe code ..

    # test that sets of attributes exactly match
    # can't rely on __eq__ for this, because __eq__ relies on Attribute.__eq__ which does not look at attributes values

    def sameValuesAs(self, other: object) -> bool:
        if not isinstance(other, AttributeCollection):
            return False

        # we sort based on packed values since the items do not
        # necessarily implement __cmp__
        def pack_(x: Attribute) -> bytes:
            return x.pack()

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

                    sval = sorted(sval, key=pack_)
                    oval = sorted(oval, key=pack_)

                if sval != oval:
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

    def __init__(self, packed: bytes, context: 'Negotiated | None' = None) -> None:
        """Create Attributes from packed bytes.

        Args:
            packed: Raw path attributes bytes (concatenated TLV attributes).
            context: Optional negotiated context for parsing.
        """
        self._packed = packed
        self._context = context
        self._parsed: AttributeCollection | None = None

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
    def packed(self) -> bytes:
        """Raw packed path attributes bytes."""
        return self._packed

    def unpack_attributes(self, negotiated: 'Negotiated | None' = None) -> AttributeCollection:
        """Lazy-unpack to semantic AttributeCollection.

        Args:
            negotiated: BGP session negotiated parameters.
                       If not provided, uses stored context.

        Returns:
            Unpacked AttributeCollection (semantic container).
        """
        if self._parsed is None:
            ctx = negotiated or self._context
            if ctx is None:
                raise RuntimeError('Attributes.unpack_attributes() requires negotiated context')
            self._parsed = AttributeCollection.unpack(self._packed, ctx)
        return self._parsed

    def __getitem__(self, code: int) -> Attribute:
        """Get attribute by code (requires prior unpack_attributes() or context)."""
        if self._parsed is None and self._context is not None:
            self.unpack_attributes(self._context)
        if self._parsed is None:
            raise RuntimeError('Must call unpack_attributes(negotiated) before accessing attributes')
        # AttributeCollection stores Attribute instances
        return cast(Attribute, self._parsed[code])

    def has(self, code: int) -> bool:
        """Check if attribute exists (requires prior unpack_attributes() or context)."""
        if self._parsed is None and self._context is not None:
            self.unpack_attributes(self._context)
        if self._parsed is None:
            raise RuntimeError('Must call unpack_attributes(negotiated) before checking attributes')
        return self._parsed.has(code)


# Backward compatibility aliases
AttributesWire = Attributes  # Old wire container name
AttributeSet = AttributeCollection  # Old semantic container name
