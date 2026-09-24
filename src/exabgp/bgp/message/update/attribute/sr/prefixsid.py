"""sr/prefixsid.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Type, TypeVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify

from exabgp.util import hexstring
from exabgp.util.types import Buffer

# =====================================================================
# draft-ietf-idr-bgp-prefix-sid
# This Attribute may contain up to 3 TLVs
# Label-Index TLV ( type = 1 ) is mandatory for this attribute.

# SR TLV type codes
SR_TLV_LABEL_INDEX: int = 1  # Label-Index TLV type
SR_TLV_SRGB: int = 3  # Segment Routing Global Block TLV type

# RFC 8669 section 6: "if a recognized TLV appears more than once in a BGP Prefix-SID
# attribute while the specification only allows for a single occurrence, then all the
# occurrences of the TLV other than the first one SHALL be discarded".  Sections 3.1 and
# 3.2 give the attribute one Label-Index and one Originator SRGB, and this document
# defines no TLV which may repeat.  An unknown type is deliberately absent: the same
# section promises unknown TLVs are "propagated unmodified", so a repeat of one is kept.
SR_SINGLE_OCCURRENCE_TLVS: frozenset[int] = frozenset((SR_TLV_LABEL_INDEX, SR_TLV_SRGB))

T = TypeVar('T', bound='PrefixSid')


@Attribute.register()
class PrefixSid(Attribute):
    ID: int = Attribute.CODE.BGP_PREFIX_SID
    FLAG: int = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    CACHING: ClassVar[bool] = True
    TLV: ClassVar[int] = -1
    # RFC 8669 section 6: a BGP Prefix-SID attribute which cannot be processed MUST be
    # ignored and not advertised onwards, which the RFC itself calls equivalent to the
    # attribute discard of RFC 7606.  Discard rather than treat-as-withdraw: the label
    # information is lost, the reachability the route carries is not.
    # AttributeCollection.parse honours this flag for both a Notify and a ValueError out of
    # the TLV walk below; without it every malformed TLV reset the session instead.
    DISCARD: ClassVar[bool] = True
    # Not a claim that an empty Prefix-SID is legal: it is the opposite, and the check at
    # the top of unpack_attribute below says so.  This takes the decision away from the
    # generic `length == 0 and not VALID_ZERO` rule in AttributeCollection.parse, which
    # answers treat-as-withdraw for every attribute.  "Not meeting the minimum attribute
    # length requirement" is the first of the three malformed shapes RFC 8669 section 6
    # names, and all three end in attribute discard, so the route must survive its
    # Prefix-SID.  Letting the decoder refuse the attribute routes it through DISCARD
    # above instead.
    VALID_ZERO: ClassVar[bool] = True

    # Registered subclasses we know how to decode
    registered_srids: ClassVar[dict[int, Type[Any]]] = dict()

    def __init__(self, sr_attrs: list[Any], packed: Buffer | None = None) -> None:
        self.sr_attrs: list[Any] = sr_attrs
        self._packed: Buffer = self._attribute(packed if packed else b''.join(_.pack_tlv() for _ in sr_attrs))

    @classmethod
    def register_sr(cls, srid: int | None = None, flag: int | None = None) -> Callable[[Type[Any]], Type[Any]]:
        def register_srid(klass: Type[Any]) -> Type[Any]:
            scode: int = klass.TLV if srid is None else srid
            if scode in cls.registered_srids:
                raise RuntimeError('only one class can be registered per Segment Routing TLV type')
            cls.registered_srids[scode] = klass
            return klass

        return register_srid

    @classmethod
    def unpack_attribute(cls: Type[T], data: Buffer, negotiated: Negotiated) -> T:
        # RFC 8669 section 6: an attribute "not meeting the minimum attribute length
        # requirement" is malformed, and the attribute must be ignored.  The smallest
        # thing this attribute can carry is one three byte TLV header, and it must carry
        # at least one, so an empty value cannot be parsed.
        if not data:
            raise Notify(3, 1, 'SR Prefix-SID attribute is empty, it must carry at least one TLV')
        sr_attrs: list[Any] = []
        # keep what the peer sent: rebuilding it from the parsed TLVs would announce
        # something else, and a TLV we do not know cannot be rebuilt at all
        original: Buffer = data
        kept: list[Buffer] = []
        single_seen: set[int] = set()
        repeat_discarded: bool = False
        while data:
            # TLV header: Type(1) + Length(2) = 3 bytes minimum
            if len(data) < 3:
                raise Notify(3, 1, f'SR Prefix-SID TLV header truncated: need 3 bytes, got {len(data)}')
            # Type = 1 octet
            scode: int = data[0]
            # L = 2 octet  :|
            length: int = unpack('!H', data[1:3])[0]
            if len(data) < length + 3:
                raise Notify(3, 1, f'SR Prefix-SID TLV truncated: need {length + 3} bytes, got {len(data)}')
            if scode in SR_SINGLE_OCCURRENCE_TLVS:
                if scode in single_seen:
                    # Discarded, and not carried onwards either.  RFC 9012 section 13 asks
                    # for the opposite of that second half for a repeated sub-TLV, which is
                    # why the two are not one helper: there the repeat is only stopped from
                    # being read, here section 6 offers propagation to unknown TLVs alone.
                    repeat_discarded = True
                    data = data[length + 3 :]
                    continue
                single_seen.add(scode)
            if scode in cls.registered_srids:
                klass: Any = cls.registered_srids[scode].unpack_attribute(data[3 : length + 3], length)
            else:
                klass = GenericSRId(scode, data[3 : length + 3])
            sr_attrs.append(klass)
            kept.append(data[: length + 3])
            data = data[length + 3 :]
        if not repeat_discarded:
            return cls(sr_attrs=sr_attrs, packed=original)
        # Rebuilt from the peer's own framing rather than from the decoded TLVs, so the
        # only difference between what arrived and what leaves is the discarded repeat.
        return cls(sr_attrs=sr_attrs, packed=b''.join(bytes(_) for _ in kept))

    def json(self, compact: bool | None = None) -> str:
        content: str = ', '.join(d.json() for d in self.sr_attrs)
        return f'{{ {content} }}'

    def __str__(self) -> str:
        # First, we try to decode path attribute for SR-MPLS
        label_index: Any | None = next((i for i in self.sr_attrs if i.TLV == 1), None)
        if label_index is not None:
            srgb: Any | None = next((i for i in self.sr_attrs if i.TLV == SR_TLV_SRGB), None)
            if srgb is not None:
                return f'[ {label_index!s}, {srgb!s} ]'
            return f'[ {label_index!s} ]'

        # if not, we try to decode path attribute for SRv6
        return '[ ' + ', '.join([str(attr) for attr in self.sr_attrs]) + ' ]'

    def pack_attribute(self, negotiated: Negotiated) -> Buffer:
        return self._packed


class GenericSRId:
    def __init__(self, code: int, rep: Buffer) -> None:
        self.rep: Buffer = rep
        self.code: int = code

    @property
    def TLV(self) -> int:
        return self.code

    def __repr__(self) -> str:
        return 'Attribute with code [ {} ] not implemented'.format(self.code)

    def pack_tlv(self) -> bytes:
        """Re-emit the TLV exactly as the peer sent it.

        Without this, PrefixSid.__init__ raised AttributeError out of the decoder for any
        TLV type which is not registered, which is every code a peer picks but 1 and 3.
        """
        return bytes([self.code]) + pack('!H', len(self.rep)) + bytes(self.rep)

    @classmethod
    def unpack_attribute(cls, scode: int, data: Buffer) -> GenericSRId:
        return cls(code=scode, rep=data)

    def json(self, compact: bool | None = None) -> str:
        return '"attribute-not-implemented-{}": "{}"'.format(self.code, hexstring(self.rep))
