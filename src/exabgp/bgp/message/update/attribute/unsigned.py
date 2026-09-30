"""unsigned.py

An attribute whose value is one unsigned integer of a fixed width: MED, LOCAL_PREF.

The width on the wire is the constraint on the value. It is declared once, as `WIDTH`, and
the range (`MAX`), the checks of `from_int` and `from_packet`, and what the configuration
says the value is (grammar/shape.py) all come from it.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

BITS_PER_OCTET = 8


class UnsignedAttribute(Attribute):
    WIDTH: ClassVar[int]  # octets on the wire
    MAX: ClassVar[int]  # the largest value, from WIDTH
    NAME: ClassVar[str]  # how an error names it

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if 'WIDTH' in vars(cls):
            cls.MAX = (1 << (BITS_PER_OCTET * cls.WIDTH)) - 1

    def __init__(self, packed: Buffer) -> None:
        """From wire-format bytes, NOT validated: use from_packet() or from_int()."""
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> Self:
        if len(data) != cls.WIDTH:
            raise ValueError(f'{cls.NAME} requires exactly {cls.WIDTH} bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def from_int(cls, value: int) -> Self:
        if not 0 <= value <= cls.MAX:
            raise ValueError(f'{cls.NAME} value out of range: {value}')
        return cls(value.to_bytes(cls.WIDTH, 'big'))

    @property
    def value(self) -> int:
        return int.from_bytes(self._packed, 'big')

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.value == other.value

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return str(self.value)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        # wire data: from_packet checks the length
        return cls.from_packet(data)
