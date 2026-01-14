"""localremoteid.py

BGP-LS Link Local/Remote Identifiers (RFC 7752, RFC 5307).

TLV 258 carries the Link Local and Remote Identifiers used to identify
unnumbered links. These identifiers correspond to IS-IS sub-TLV 4
within TLV 22 (RFC 5307).

Wire format (8 bytes):
   0                   1                   2                   3
   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |                  Link Local Identifier                        |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |                  Link Remote Identifier                       |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

If the Link Remote Identifier is unknown, it is set to 0.

Based on work by Klaus Schneider (https://github.com/klausps).
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState, BaseLS
from exabgp.util.types import Buffer

# 32-bit maximum value (0xFFFFFFFF)
_MAX_32BIT: int = 4294967295


@LinkState.register_lsid(tlv=258, json_key='link-local-remote-identifiers', repr_name='Link Local/Remote Identifiers')
class LinkLocalRemoteId(BaseLS):
    LEN = 8

    @property
    def content(self) -> dict[str, int]:
        """Unpack local and remote identifiers from packed bytes."""
        local_id, remote_id = unpack('!II', self._packed)
        return {'local-id': local_id, 'remote-id': remote_id}

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> LinkLocalRemoteId:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_link_identifiers(cls, local_id: int, remote_id: int = 0) -> LinkLocalRemoteId:
        """Factory method to create LinkLocalRemoteId.

        Args:
            local_id: Link local identifier (0-4294967295)
            remote_id: Link remote identifier (0-4294967295), 0 if unknown
        """
        if not 0 <= local_id <= _MAX_32BIT:
            raise ValueError(f'local_id must be 0-{_MAX_32BIT}, got {local_id}')
        if not 0 <= remote_id <= _MAX_32BIT:
            raise ValueError(f'remote_id must be 0-{_MAX_32BIT}, got {remote_id}')
        return cls(pack('!II', local_id, remote_id))
