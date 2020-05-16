# encoding: utf-8
"""
protection.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LsGenericFlags

#       0                   1
#       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |Protection Cap |    Reserved   |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      https://tools.ietf.org/html/rfc5307 Sec 1.2
#      0x01  Extra Traffic
#      0x02  Unprotected
#      0x04  Shared
#      0x08  Dedicated 1:1
#      0x10  Dedicated 1+1
#      0x20  Enhanced
#      0x40  Reserved
#      0x80  Reserved


@LINKSTATE.register()
class LinkProtectionType(LsGenericFlags):
    REPR = 'Link protection mask'
    JSON = 'link-protection-flags'
    TLV = 1093
    FLAGS = [
        'ExtraTrafic',
        'Unprotected',
        'Shared',
        'Dedicated 1:1',
        'Dedicated 1+1',
        'Enhanced',
        'RSV',
        'RSV',
    ]
    LEN = 2
