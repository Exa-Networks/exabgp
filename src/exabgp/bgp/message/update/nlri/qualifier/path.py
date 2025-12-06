"""bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from typing import Any, ClassVar


# ===================================================================== PathInfo
# RFC draft-ietf-idr-add-paths-09


class PathInfo:
    __slots__ = ('_packed', '_disabled')

    LENGTH = 4  # Path info is always 4 bytes
    NOPATH: ClassVar['PathInfo']
    DISABLED: ClassVar['PathInfo']

    def __init__(self, packed: bytes) -> None:
        if packed and len(packed) != self.LENGTH:
            raise ValueError(f'PathInfo requires exactly {self.LENGTH} bytes, got {len(packed)}')
        self._packed = packed
        self._disabled = False

    @classmethod
    def make_from_integer(cls, integer: int) -> 'PathInfo':
        """Create PathInfo from integer value."""
        packed = b''.join(bytes([(integer >> offset) & 0xFF]) for offset in [24, 16, 8, 0])
        return cls(packed)

    @classmethod
    def make_from_ip(cls, ip: str) -> 'PathInfo':
        """Create PathInfo from IP-style string (e.g., '1.2.3.4')."""
        packed = b''.join(bytes([int(_)]) for _ in ip.split('.'))
        return cls(packed)

    @property
    def path_info(self) -> bytes:
        return self._packed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PathInfo):
            return False
        return self._packed == other._packed

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __len__(self) -> int:
        return len(self._packed)

    def json(self) -> str:
        if self._disabled:
            return ''
        if self._packed:
            return '"path-information": "{}"'.format('.'.join([str(_) for _ in self._packed]))
        # NOPATH: ADD-PATH enabled but no specific ID set - wire format is 0.0.0.0
        return '"path-information": "0.0.0.0"'

    def __repr__(self) -> str:
        if self._disabled:
            return ''
        if self._packed:
            return ' path-information {}'.format('.'.join([str(_) for _ in self._packed]))
        # NOPATH: ADD-PATH enabled but no specific ID set - wire format is 0.0.0.0
        return ' path-information 0.0.0.0'

    def pack_path(self) -> bytes:
        if self._disabled:
            return b''
        if self._packed:
            return self._packed
        return b'\x00\x00\x00\x00'

    def __copy__(self) -> 'PathInfo':
        """Preserve singleton identity for NOPATH and DISABLED."""
        if self is PathInfo.NOPATH or self is PathInfo.DISABLED:
            return self
        # Regular PathInfo: create a new instance with same data
        new = PathInfo.__new__(PathInfo)
        new._disabled = self._disabled
        new._packed = self._packed
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'PathInfo':
        """Preserve singleton identity for NOPATH and DISABLED."""
        if self is PathInfo.NOPATH or self is PathInfo.DISABLED:
            return self
        # Regular PathInfo: create a new instance with same data
        # _packed is bytes (immutable), so no need to deepcopy it
        new = PathInfo.__new__(PathInfo)
        new._disabled = self._disabled
        new._packed = self._packed
        memo[id(self)] = new
        return new

    @classmethod
    def _create_nopath(cls) -> 'PathInfo':
        """Create the NOPATH sentinel. Called once at module load.

        Used when ADD-PATH is enabled but no specific path ID is set.
        pack_path() returns 4 zero bytes, but json()/repr() return empty.
        """
        instance = object.__new__(cls)
        instance._disabled = False
        instance._packed = b''
        return instance

    @classmethod
    def _create_disabled(cls) -> 'PathInfo':
        """Create the DISABLED sentinel. Called once at module load.

        Used when ADD-PATH capability is not negotiated.
        """
        instance = object.__new__(cls)
        instance._disabled = True
        instance._packed = b''
        return instance


PathInfo.NOPATH = PathInfo._create_nopath()
PathInfo.DISABLED = PathInfo._create_disabled()
