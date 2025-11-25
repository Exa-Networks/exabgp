"""attribute.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Optional, Tuple, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.notification import Notify

from exabgp.util.cache import Cache

# Attribute length encoding constants
ATTR_LENGTH_EXTENDED_MAX: int = 0xFF  # Maximum length for non-extended encoding (255)

# ============================================================== TreatAsWithdraw
#


class TreatAsWithdraw:
    ID: ClassVar[int] = 0xFFFF
    GENERIC: ClassVar[bool] = False

    aid: Optional[int]

    def __init__(self, aid: Optional[int] = None) -> None:
        self.aid = aid

    def __str__(self) -> str:
        if self.aid is None:
            return 'treat-as-withdraw'
        return 'treat-as-withdraw due to {}'.format(Attribute.CODE(self.aid))


class Discard:
    ID: ClassVar[int] = 0xFFFE
    GENERIC: ClassVar[bool] = False

    aid: Optional[int]

    def __init__(self, aid: Optional[int] = None) -> None:
        self.aid = aid

    def __str__(self) -> str:
        if self.aid is None:
            return 'discard'
        return 'discard due to {}'.format(Attribute.CODE(self.aid))


# ==================================================================== Attribute
#


class Attribute:
    # we need to define ID and FLAG inside of the subclasses
    ID: ClassVar[int] = 0x00
    FLAG: ClassVar[int] = 0x00

    # Should this Attribute be cached
    CACHING: ClassVar[bool] = False
    # Generic Class or implementation
    GENERIC: ClassVar[bool] = False

    # Attribute behavior flags (RFC-based defaults)
    # RFC 7606: malformed attribute handling - treat UPDATE as withdraw
    TREAT_AS_WITHDRAW: ClassVar[bool] = False
    # RFC 7606: silently discard malformed attribute
    DISCARD: ClassVar[bool] = False
    # RFC 4271: required in UPDATE message
    MANDATORY: ClassVar[bool] = False
    # Only one instance of this attribute allowed per UPDATE
    NO_DUPLICATE: ClassVar[bool] = False
    # Zero-length value is valid for this attribute
    VALID_ZERO: ClassVar[bool] = False
    # Skip this attribute in text/JSON output generation
    NO_GENERATION: ClassVar[bool] = False

    # Registered subclasses we know how to decode
    registered_attributes: ClassVar[Dict[Tuple[int, int], Type[Attribute]]] = dict()

    # what this implementation knows as attributes
    attributes_known: ClassVar[List[int]] = []
    attributes_well_know: ClassVar[List[int]] = []
    attributes_optional: ClassVar[List[int]] = []

    # Are we caching Attributes (configuration)
    caching: ClassVar[bool] = False

    # The attribute cache per attribute ID
    cache: ClassVar[Dict[int, Cache]] = {}

    # ---------------------------------------------------------------------------

    # XXX: FIXME: The API of ID is a bit different (it can be instanciated)
    # XXX: FIXME: This is legacy. should we change to not be ?
    class CODE(int):
        # This should move within the classes and not be here
        # RFC 4271
        ORIGIN: ClassVar[int] = 0x01
        AS_PATH: ClassVar[int] = 0x02
        NEXT_HOP: ClassVar[int] = 0x03
        MED: ClassVar[int] = 0x04
        LOCAL_PREF: ClassVar[int] = 0x05
        ATOMIC_AGGREGATE: ClassVar[int] = 0x06
        AGGREGATOR: ClassVar[int] = 0x07
        # RFC 1997
        COMMUNITY: ClassVar[int] = 0x08
        # RFC 4456
        ORIGINATOR_ID: ClassVar[int] = 0x09
        CLUSTER_LIST: ClassVar[int] = 0x0A  # 10
        # RFC 4760
        MP_REACH_NLRI: ClassVar[int] = 0x0E  # 14
        MP_UNREACH_NLRI: ClassVar[int] = 0x0F  # 15
        # RFC 4360
        EXTENDED_COMMUNITY: ClassVar[int] = 0x10  # 16
        # RFC 4893
        AS4_PATH: ClassVar[int] = 0x11  # 17
        AS4_AGGREGATOR: ClassVar[int] = 0x12  # 18
        # RFC6514
        PMSI_TUNNEL: ClassVar[int] = 0x16  # 22
        # RFC5512
        TUNNEL_ENCAP: ClassVar[int] = 0x17  # 23
        # RFC5701
        IPV6_EXTENDED_COMMUNITY: ClassVar[int] = 0x19  # 25
        AIGP: ClassVar[int] = 0x1A  # 26
        # RFC7752
        BGP_LS: ClassVar[int] = 0x1D  # 29
        # draft-ietf-idr-large-community
        LARGE_COMMUNITY: ClassVar[int] = 0x20  # 32
        # draft-ietf-idr-bgp-prefix-sid
        BGP_PREFIX_SID: ClassVar[int] = 0x28  # 40

        INTERNAL_NAME: ClassVar[int] = 0xFFFA
        INTERNAL_WITHDRAW: ClassVar[int] = 0xFFFB
        INTERNAL_WATCHDOG: ClassVar[int] = 0xFFFC
        INTERNAL_SPLIT: ClassVar[int] = 0xFFFD
        INTERNAL_DISCARD: ClassVar[int] = 0xFFFE
        INTERNAL_TREAT_AS_WITHDRAW: ClassVar[int] = 0xFFFF  # Treat as Withdraw

        # Currently formatting is done with %-18s
        names: ClassVar[Dict[int, str]] = {
            ORIGIN: 'origin',
            AS_PATH: 'as-path',
            NEXT_HOP: 'next-hop',
            MED: 'med',  # multi-exit-disc
            LOCAL_PREF: 'local-preference',
            ATOMIC_AGGREGATE: 'atomic-aggregate',
            AGGREGATOR: 'aggregator',
            COMMUNITY: 'community',
            LARGE_COMMUNITY: 'large-community',
            ORIGINATOR_ID: 'originator-id',
            CLUSTER_LIST: 'cluster-list',
            MP_REACH_NLRI: 'mp-reach-nlri',  # multi-protocol reacheable nlri
            MP_UNREACH_NLRI: 'mp-unreach-nlri',  # multi-protocol unreacheable nlri
            EXTENDED_COMMUNITY: 'extended-community',
            IPV6_EXTENDED_COMMUNITY: 'extended-community-ipv6',
            AS4_PATH: 'as4-path',
            AS4_AGGREGATOR: 'as4-aggregator',
            PMSI_TUNNEL: 'pmsi-tunnel',
            TUNNEL_ENCAP: 'tunnel-encaps',
            AIGP: 'aigp',
            BGP_LS: 'bgp-ls',
            BGP_PREFIX_SID: 'bgp-prefix-sid',
            0xFFFA: 'internal-name',
            0xFFFB: 'internal-withdraw',
            0xFFFC: 'internal-watchdog',
            0xFFFD: 'internal-split',
            0xFFFE: 'internal-discard',
            0xFFFF: 'internal-treath-as-withdraw',
        }

        def __repr__(self) -> str:
            return self.names.get(self, 'unknown-attribute-{}'.format(hex(self)))

        def __str__(self) -> str:
            return repr(self)

        @classmethod
        def name(cls, self: int) -> str:
            return cls.names.get(self, 'unknown-attribute-{}'.format(hex(self)))

    # ---------------------------------------------------------------------------

    class Flag(int):
        EXTENDED_LENGTH: ClassVar[int] = 0x10  # .  16 - 0001 0000
        PARTIAL: ClassVar[int] = 0x20  # .  32 - 0010 0000
        TRANSITIVE: ClassVar[int] = 0x40  # .  64 - 0100 0000
        OPTIONAL: ClassVar[int] = 0x80  # . 128 - 1000 0000

        MASK_EXTENDED: ClassVar[int] = 0xEF  # . 239 - 1110 1111
        MASK_PARTIAL: ClassVar[int] = 0xDF  # . 223 - 1101 1111
        MASK_TRANSITIVE: ClassVar[int] = 0xBF  # . 191 - 1011 1111
        MASK_OPTIONAL: ClassVar[int] = 0x7F  # . 127 - 0111 1111

        def __str__(self) -> str:
            r: List[str] = []
            v: int = int(self)
            if v & 0x10:
                r.append('EXTENDED_LENGTH')
                v -= 0x10
            if v & 0x20:
                r.append('PARTIAL')
                v -= 0x20
            if v & 0x40:
                r.append('TRANSITIVE')
                v -= 0x40
            if v & 0x80:
                r.append('OPTIONAL')
                v -= 0x80
            if v:
                r.append('UNKNOWN {}'.format(hex(v)))
            return ' '.join(r)

        def matches(self, value: int) -> bool:
            return bool(self | 0x10 == value | 0x10)

    # ---------------------------------------------------------------------------

    @classmethod
    def _attribute(klass, value: bytes) -> bytes:
        flag: int = klass.FLAG
        if flag & Attribute.Flag.OPTIONAL and not value:
            return b''
        length: int = len(value)
        if length > ATTR_LENGTH_EXTENDED_MAX:
            flag |= Attribute.Flag.EXTENDED_LENGTH
        len_value: bytes
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            len_value = pack('!H', length)
        else:
            len_value = bytes([length])
        return bytes([flag, klass.ID]) + len_value + value

    def _len(self, value: bytes) -> int:
        length: int = len(value)
        return length + 3 if length <= ATTR_LENGTH_EXTENDED_MAX else length + 4

    def __eq__(self, other: Any) -> bool:
        return bool(self.ID == other.ID and self.FLAG == other.FLAG)

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: Any) -> bool:
        return bool(self.ID < other.ID)

    def __le__(self, other: Any) -> bool:
        return bool(self.ID <= other.ID)

    def __gt__(self, other: Any) -> bool:
        return bool(self.ID > other.ID)

    def __ge__(self, other: Any) -> bool:
        return bool(self.ID >= other.ID)

    @classmethod
    def register(
        cls, attribute_id: Optional[int] = None, flag: Optional[int] = None
    ) -> Callable[[Type[Attribute]], Type[Attribute]]:
        def register_attribute(klass: Type[Attribute]) -> Type[Attribute]:
            aid: int = klass.ID if attribute_id is None else attribute_id
            flg: int = (
                klass.FLAG | Attribute.Flag.EXTENDED_LENGTH if flag is None else flag | Attribute.Flag.EXTENDED_LENGTH
            )
            if (aid, flg) in cls.registered_attributes:
                raise RuntimeError('only one class can be registered per attribute')
            cls.registered_attributes[(aid, flg)] = klass
            cls.attributes_known.append(aid)
            if klass.FLAG & Attribute.Flag.OPTIONAL:
                cls.attributes_optional.append(aid)
            else:
                cls.attributes_well_know.append(aid)
            return klass

        return register_attribute

    @classmethod
    def registered(cls, attribute_id: int, flag: int) -> bool:
        return (attribute_id, flag | Attribute.Flag.EXTENDED_LENGTH) in cls.registered_attributes

    @classmethod
    def klass(cls, attribute_id: int, flag: int) -> Type[Attribute]:
        key: Tuple[int, int] = (attribute_id, flag | Attribute.Flag.EXTENDED_LENGTH)
        if key in cls.registered_attributes:
            kls: Type[Attribute] = cls.registered_attributes[key]
            kls.ID = attribute_id
            return kls

        raise Notify(2, 4, 'can not handle attribute id {}'.format(attribute_id))

    @classmethod
    def klass_by_id(cls, attribute_id: int) -> Optional[Type[Attribute]]:
        """Get attribute class by ID, ignoring flag variations."""
        for (registered_aid, _), klass in cls.registered_attributes.items():
            if registered_aid == attribute_id:
                return klass
        return None

    @classmethod
    def unpack(cls, attribute_id: int, flag: int, data: bytes, negotiated: Negotiated) -> Attribute:
        cache: bool = cls.caching and cls.CACHING

        if cache and data in cls.cache.get(cls.ID, {}):
            return cls.cache[cls.ID].retrieve(data)  # type: ignore[no-any-return]

        key: Tuple[int, int] = (attribute_id, flag | Attribute.Flag.EXTENDED_LENGTH)
        if key in Attribute.registered_attributes.keys():
            instance: Attribute = cls.klass(attribute_id, flag).unpack_attribute(data, negotiated)  # type: ignore[attr-defined]

            if cache:
                cls.cache[cls.ID].cache(data, instance)
            return instance

        raise Notify(2, 4, 'can not handle attribute id {}'.format(attribute_id))

    @classmethod
    def setCache(cls) -> None:
        if not cls.cache:
            for attribute in Attribute.CODE.names:
                if attribute not in cls.cache:
                    cls.cache[attribute] = Cache()


Attribute.setCache()
