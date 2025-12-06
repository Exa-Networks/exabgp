"""admingroup.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS


@LinkState.register_lsid()
class AdminGroup(BaseLS):
    TLV = 1088
    REPR = 'Admin Group mask'
    JSON = 'admin-group-mask'
    LEN = 4

    @property
    def content(self) -> int:
        """Unpack and return the admin group mask from packed bytes."""
        value: int = unpack('!L', self._packed[:4])[0]
        return value

    @classmethod
    def make_admingroup(cls, mask: int) -> AdminGroup:
        """Factory method to create AdminGroup from mask value."""
        return cls(pack('!I', mask))

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> AdminGroup:
        cls.check(data)
        return cls(data)
