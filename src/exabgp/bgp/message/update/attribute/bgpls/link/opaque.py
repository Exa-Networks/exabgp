# encoding: utf-8
"""
opaque.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

#
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |              Type             |             Length            |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    //                     Opaque link attributes (variable)       //
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.6 Opaque Link Attribute TLV
#
# This TLV is added here for completeness but we don't look into the TLV.


@LinkState.register()
class LinkOpaque(object):
    TLV = 1097
    REPR = 'Opaque Link attribute'
    REPR = 'opaque-link'

    @classmethod
    def unpack(cls, data):
        length = len(data)
        return cls(unpack('!%ds' % length, data)[0])
