"""linkid.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from struct import pack
from struct import unpack


#       0                   1                   2                   3
#       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |                  Link Local Identifier                        |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |                  Link Remote Identifier                       |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      https://tools.ietf.org/html/rfc5307 sec 1.1
# ================================================================== Link Local/Remote Identifiers


LINK_IDENTIFIER_SIZE = 8  # local(4) + remote(4)


class LinkIdentifier:
    def __init__(self, local_id, remote_id, packed=None):
        self.local_id = local_id
        self.remote_id = remote_id
        # a LinkIdentifier with no packed form is falsy (__len__ is 0) and the caller
        # silently drops it, losing a well formed identifier.  Keep the wire form.
        self._packed = packed if packed is not None else pack('!LL', local_id, remote_id)

    @classmethod
    def unpack(cls, data):
        if len(data) < LINK_IDENTIFIER_SIZE:
            raise Notify(
                3,
                10,
                'invalid BGP-LS link identifier sub-TLV, expected %d bytes, got %d' % (LINK_IDENTIFIER_SIZE, len(data)),
            )
        local_id = unpack('!L', data[:4])[0]
        remote_id = unpack('!L', data[4:8])[0]
        return cls(local_id=local_id, remote_id=remote_id, packed=data[:LINK_IDENTIFIER_SIZE])

    def json(self):
        # rendered inside a JSON array, so each entry must be a self contained object
        return '{{ "link-local-id": {}, "link-remote-id": {} }}'.format(self.local_id, self.remote_id)

    def as_dict(self):
        return {'link-local-id': self.local_id, 'link-remote-id': self.remote_id}

    def __eq__(self, other):
        if not isinstance(other, LinkIdentifier):
            return NotImplemented
        return (self.local_id == other.local_id) and (self.remote_id == other.remote_id)

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        raise RuntimeError('Not implemented')

    def __le__(self, other):
        raise RuntimeError('Not implemented')

    def __gt__(self, other):
        raise RuntimeError('Not implemented')

    def __ge__(self, other):
        raise RuntimeError('Not implemented')

    def __str__(self):
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        if not self._packed:
            return 0
        return len(self._packed)

    def __hash__(self):
        return hash(str(self))

    def pack(self):
        return self._packed
