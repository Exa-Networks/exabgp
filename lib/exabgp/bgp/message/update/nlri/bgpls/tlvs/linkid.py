# encoding: utf-8
"""
linkid.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.util import ordinal

#       0                   1                   2                   3
#       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |                  Link Local Identifier                        |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |                  Link Remote Identifier                       |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      https://tools.ietf.org/html/rfc5307 sec 1.1
# ================================================================== Link Local/Remote Identifiers


class LinkIdentifier(object):
    def __init__(self, local_id, remote_id, packed=None):
        self.local_id = local_id
        self.remote_id = remote_id
        self._packed = packed

    @classmethod
    def unpack(cls, data):
        local_id = unpack('!L', data[:4])[0]
        remote_id = unpack('!L', data[4:8])[0]
        return cls(local_id=local_id, remote_id=remote_id)

    def json(self):
        content = '"link-local-id": %s, ' % self.local_id + '"link-remote-id": %s' % self.remote_id
        return content

    def __eq__(self, other):
        return (self.local_id == other.local_id) and (self.remote_id == other.remote_id)

    def __neq__(self, other):
        return self.local_id != other.local_id

    def __lt__(self, other):
        raise RuntimeError('Not implemented')

    def __le__(self, other):
        raise RuntimeError('Not implemented')

    def __gt__(self, other):
        raise RuntimeError('Not implemented')

    def __ge__(self, other):
        raise RuntimeError('Not implemented')

    def __str__(self):
        return ':'.join('%02X' % ordinal(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self._packed)

    def __hash__(self):
        return hash(str(self))

    def pack(self):
        return self._packed
