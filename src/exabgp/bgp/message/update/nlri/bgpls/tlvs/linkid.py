"""linkid.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.bgp.message.notification import Notify
from exabgp.util.types import Buffer


#       0                   1                   2                   3
#       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |                  Link Local Identifier                        |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |                  Link Remote Identifier                       |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      https://tools.ietf.org/html/rfc5307 sec 1.1
# ================================================================== Link Local/Remote Identifiers


LINK_ID_SIZE = 8  # RFC 5307 3.1: a 4 byte local and a 4 byte remote identifier


class LinkIdentifier:
    def __init__(self, local_id: int, remote_id: int, packed: Buffer | None = None) -> None:
        self.local_id = local_id
        self.remote_id = remote_id
        self._packed = packed if packed is not None else pack('!LL', local_id, remote_id)

    @classmethod
    def unpack_linkid(cls, data: Buffer) -> 'LinkIdentifier':
        # RFC 5307 3.1: two 4 byte identifiers.  Reading them from a shorter payload
        # raised struct.error out of json(), long after the message was accepted.
        if len(data) < LINK_ID_SIZE:
            raise Notify(3, 10, f'BGP-LS link identifier sub-tlv is {len(data)} bytes, expected {LINK_ID_SIZE}')
        local_id = unpack('!L', data[:4])[0]
        remote_id = unpack('!L', data[4:8])[0]
        return cls(local_id=local_id, remote_id=remote_id, packed=data[:LINK_ID_SIZE])

    def json(self) -> str:
        return f'{{ "link-local-id": {self.local_id}, "link-remote-id": {self.remote_id} }}'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LinkIdentifier):
            return NotImplemented
        return self.local_id == other.local_id and self.remote_id == other.remote_id

    def __lt__(self, other: LinkIdentifier) -> bool:
        raise RuntimeError('Not implemented')

    def __le__(self, other: LinkIdentifier) -> bool:
        raise RuntimeError('Not implemented')

    def __gt__(self, other: LinkIdentifier) -> bool:
        raise RuntimeError('Not implemented')

    def __ge__(self, other: LinkIdentifier) -> bool:
        raise RuntimeError('Not implemented')

    def __str__(self) -> str:
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self) -> int:
        if not self._packed:
            return 0
        return len(self._packed)

    def __hash__(self) -> int:
        return hash(str(self))

    def pack_tlv(self) -> Buffer:
        return self._packed
