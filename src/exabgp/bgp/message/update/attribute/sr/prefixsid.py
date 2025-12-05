"""sr/prefixsid.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Type, TypeVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify

from exabgp.util import hexstring

# =====================================================================
# draft-ietf-idr-bgp-prefix-sid
# This Attribute may contain up to 3 TLVs
# Label-Index TLV ( type = 1 ) is mandatory for this attribute.

# SR TLV type codes
SR_TLV_SRGB: int = 3  # Segment Routing Global Block TLV type

T = TypeVar('T', bound='PrefixSid')


@Attribute.register()
class PrefixSid(Attribute):
    ID: ClassVar[int] = Attribute.CODE.BGP_PREFIX_SID
    FLAG: ClassVar[int] = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    CACHING: ClassVar[bool] = True
    TLV: ClassVar[int] = -1

    # Registered subclasses we know how to decode
    registered_srids: ClassVar[dict[int, Type[Any]]] = dict()

    def __init__(self, sr_attrs: list[Any], packed: bytes | None = None) -> None:
        self.sr_attrs: list[Any] = sr_attrs
        self._packed: bytes = self._attribute(packed if packed else b''.join(_.pack_tlv() for _ in sr_attrs))

    @classmethod
    def register(cls, srid: int | None = None, flag: int | None = None) -> Callable[[Type[Any]], Type[Any]]:
        def register_srid(klass: Type[Any]) -> Type[Any]:
            scode: int = klass.TLV if srid is None else srid
            if scode in cls.registered_srids:
                raise RuntimeError('only one class can be registered per Segment Routing TLV type')
            cls.registered_srids[scode] = klass
            return klass

        return register_srid

    @classmethod
    def unpack_attribute(cls: Type[T], data: bytes, negotiated: Negotiated) -> T:
        sr_attrs: list[Any] = []
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
            if scode in cls.registered_srids:
                klass: Any = cls.registered_srids[scode].unpack_attribute(data[3 : length + 3], length)
            else:
                klass = GenericSRId(scode, data[3 : length + 3])
            klass.TLV = scode
            sr_attrs.append(klass)
            data = data[length + 3 :]
        return cls(sr_attrs=sr_attrs)

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

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return self._packed


class GenericSRId:
    TLV: ClassVar[int] = 99998

    def __init__(self, code: int, rep: bytes) -> None:
        self.rep: bytes = rep
        self.code: int = code

    def __repr__(self) -> str:
        return 'Attribute with code [ {} ] not implemented'.format(self.code)

    @classmethod
    def unpack_attribute(cls, scode: int, data: bytes) -> GenericSRId:
        return cls(code=scode, rep=data)

    def json(self, compact: bool | None = None) -> str:
        return '"attribute-not-implemented-{}": "{}"'.format(self.code, hexstring(self.rep))
