# encoding: utf-8
"""
nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE, LsGenericFlags

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |O|T|E|B|R|V| Rsvd|
#     +-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752 Sec 3.3.1.1.  Node Flag Bits TLV
#        +-----------------+-------------------------+------------+
#        |       Bit       | Description             | Reference  |
#        +-----------------+-------------------------+------------+
#        |       'O'       | Overload Bit            | [ISO10589] |
#        |       'T'       | Attached Bit            | [ISO10589] |
#        |       'E'       | External Bit            | [RFC2328]  |
#        |       'B'       | ABR Bit                 | [RFC2328]  |
#        |       'R'       | Router Bit              | [RFC5340]  |
#        |       'V'       | V6 Bit                  | [RFC5340]  |
#        | Reserved (Rsvd) | Reserved for future use |            |
#        +-----------------+-------------------------+------------+
# 		https://tools.ietf.org/html/rfc7752 sec 3.3.1.1 Node Flag Bits Definitions


@LINKSTATE.register()
class NodeFlags(object):
    TLV = 1024

    def __init__(self, nodeflags):
        self.nodeflags = nodeflags

    def __repr__(self):
        return "nodeflags: %s" % (self.nodeflags)

    @classmethod
    def unpack(cls, data, length):

        if length > 1:
            raise Notify(3, 5, "Node Flags TLV length too large")
        else:
            flags = LsGenericFlags.unpack(data[0:1], LsGenericFlags.LS_NODE_FLAGS)
        return cls(nodeflags=flags)

    def json(self, compact=None):
        return '"node-flags": {}'.format(self.nodeflags.json())
