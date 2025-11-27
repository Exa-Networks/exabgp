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
    NOPATH: ClassVar['PathInfo']
    DISABLED: ClassVar['PathInfo']

    def __init__(self, packed: bytes | None = None, integer: int | None = None, ip: str | None = None) -> None:
        self._disabled = False
        if packed:
            self.path_info: bytes = packed
        elif ip:
            self.path_info = b''.join(bytes([int(_)]) for _ in ip.split('.'))
        elif integer:
            self.path_info = b''.join(bytes([(integer >> offset) & 0xFF]) for offset in [24, 16, 8, 0])
        else:
            self.path_info = b''
        # sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PathInfo):
            return False
        return self.path_info == other.path_info

    def __neq__(self, other: object) -> bool:
        if not isinstance(other, PathInfo):
            return True
        return self.path_info != other.path_info

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __len__(self) -> int:
        return len(self.path_info)

    def json(self) -> str:
        if self._disabled:
            return ''
        if self.path_info:
            return '"path-information": "{}"'.format('.'.join([str(_) for _ in self.path_info]))
        # NOPATH: ADD-PATH enabled but no specific ID set - wire format is 0.0.0.0
        return '"path-information": "0.0.0.0"'

    def __repr__(self) -> str:
        if self._disabled:
            return ''
        if self.path_info:
            return ' path-information {}'.format('.'.join([str(_) for _ in self.path_info]))
        # NOPATH: ADD-PATH enabled but no specific ID set - wire format is 0.0.0.0
        return ' path-information 0.0.0.0'

    def pack_path(self) -> bytes:
        if self._disabled:
            return b''
        if self.path_info:
            return self.path_info
        return b'\x00\x00\x00\x00'

    def __copy__(self) -> 'PathInfo':
        """Preserve singleton identity for NOPATH and DISABLED."""
        if self is PathInfo.NOPATH or self is PathInfo.DISABLED:
            return self
        # Regular PathInfo: create a new instance with same data
        new = PathInfo.__new__(PathInfo)
        new._disabled = self._disabled
        new.path_info = self.path_info
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'PathInfo':
        """Preserve singleton identity for NOPATH and DISABLED."""
        if self is PathInfo.NOPATH or self is PathInfo.DISABLED:
            return self
        # Regular PathInfo: create a new instance with same data
        # path_info is bytes (immutable), so no need to deepcopy it
        new = PathInfo.__new__(PathInfo)
        new._disabled = self._disabled
        new.path_info = self.path_info
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
        instance.path_info = b''
        return instance

    @classmethod
    def _create_disabled(cls) -> 'PathInfo':
        """Create the DISABLED sentinel. Called once at module load.

        Used when ADD-PATH capability is not negotiated.
        """
        instance = object.__new__(cls)
        instance._disabled = True
        instance.path_info = b''
        return instance


PathInfo.NOPATH = PathInfo._create_nopath()
PathInfo.DISABLED = PathInfo._create_disabled()
