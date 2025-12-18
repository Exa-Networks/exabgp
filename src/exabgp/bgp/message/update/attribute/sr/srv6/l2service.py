"""srv6/l2service.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack
from typing import Any, Callable, ClassVar, Protocol, Type, TypeVar

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.srv6.generic import GenericSrv6ServiceSubTlv
from exabgp.util.types import Buffer


class HasTLV(Protocol):
    """Protocol for classes with TLV class attribute and unpack_attribute method."""

    TLV: ClassVar[int]

    @classmethod
    def unpack_attribute(cls, data: Buffer, length: int) -> Any: ...


# TypeVar for classes with TLV attribute
SubTlvType = TypeVar('SubTlvType', bound=HasTLV)

# 2.  SRv6 Services TLVs
#
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   TLV Type    |         TLV Length            |   RESERVED    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   SRv6 Service Sub-TLVs                                      //
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                   Figure 1: SRv6 Service TLVs


@PrefixSid.register_sr()
class Srv6L2Service:
    TLV: ClassVar[int] = 6

    # Registry maps TLV codes to Sub-TLV classes (uses HasTLV protocol)
    registered_subtlvs: ClassVar[dict[int, Type[HasTLV]]] = dict()

    def __init__(self, subtlvs: list[Any], packed: Buffer | None = None) -> None:
        """Initialize L2 Service TLV.

        Args:
            subtlvs: List of sub-TLVs (Srv6SidInformation or GenericSrv6ServiceSubTlv)
            packed: Optional pre-packed wire format
        """
        self.subtlvs: list[Any] = subtlvs
        self.packed: Buffer = self.pack_tlv()

    @classmethod
    def register(cls) -> Callable[[Type[SubTlvType]], Type[SubTlvType]]:
        def register_subtlv(klass: Type[SubTlvType]) -> Type[SubTlvType]:
            scode: int = klass.TLV
            if scode in cls.registered_subtlvs:
                raise RuntimeError('only one class can be registered per SRv6 Service Sub-TLV type')
            cls.registered_subtlvs[scode] = klass
            return klass

        return register_subtlv

    @classmethod
    def unpack_attribute(cls, data: Buffer, length: int) -> Srv6L2Service:
        subtlvs: list[GenericSrv6ServiceSubTlv] = []

        # Need at least 1 byte for reserved field
        if len(data) < 1:
            raise Notify(3, 1, 'SRv6 L2 Service TLV too short: need at least 1 byte')

        # First byte is reserved
        data = data[1:]
        while data:
            # Sub-TLV header: type(1) + length(2) = 3 bytes minimum
            if len(data) < 3:
                raise Notify(3, 1, f'SRv6 L2 Service Sub-TLV header truncated: need 3 bytes, got {len(data)}')
            code: int = data[0]
            length = unpack('!H', data[1:3])[0]
            if len(data) < length + 3:
                raise Notify(3, 1, f'SRv6 L2 Service Sub-TLV truncated: need {length + 3} bytes, got {len(data)}')
            if code in cls.registered_subtlvs:
                subtlv: GenericSrv6ServiceSubTlv = cls.registered_subtlvs[code].unpack_attribute(
                    data[3 : length + 3], length
                )
            else:
                subtlv = GenericSrv6ServiceSubTlv(data[3 : length + 3], code)
            subtlvs.append(subtlv)
            data = data[length + 3 :]

        return cls(subtlvs=subtlvs)

    def pack_tlv(self) -> bytes:
        subtlvs_packed: bytes = b''.join([_.pack_tlv() for _ in self.subtlvs])
        length: int = len(subtlvs_packed) + 1
        reserved: int = 0

        return pack('!B', self.TLV) + pack('!H', length) + pack('!B', reserved) + subtlvs_packed

    def __str__(self) -> str:
        return 'l2-service [ ' + ', '.join([str(subtlv) for subtlv in self.subtlvs]) + ' ]'

    def json(self, compact: bool | None = None) -> str:
        content: str = '[ ' + ', '.join(subtlv.json() for subtlv in self.subtlvs) + ' ]'
        return '"l2-service": {}'.format(content)
