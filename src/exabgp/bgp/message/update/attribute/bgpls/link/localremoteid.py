# encoding: utf-8
"""
localremoteid.py

Created by Klaus Schneider.
https://github.com/klausps
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS


# 258 - Link Local/Remote Identifiers (RFC 5307 carried in BGP-LS per RFC 7752)
# Value length: 8 bytes -> Local Identifier (4 bytes) + Remote Identifier (4 bytes)
@LinkState.register()
class LinkLocalRemoteIdentifiers(BaseLS):
    TLV = 258
    REPR = 'Link Local/Remote Identifiers'
    JSON = 'link-local-remote-identifiers'
    LEN = 8

    @classmethod
    def unpack(cls, data):
        cls.check(data)
        local_id, remote_id = unpack('!II', data)
        return cls({'local-id': local_id, 'remote-id': remote_id})
