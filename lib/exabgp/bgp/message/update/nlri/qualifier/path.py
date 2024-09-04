# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes_i


# ===================================================================== PathInfo
# RFC draft-ietf-idr-add-paths-09


class PathInfo(object):

    __slots__ = ['path_info']

    def __init__(self, packed=None, integer=None, ip=None):
        if packed:
            self.path_info = packed
        elif ip:
            self.path_info = concat_bytes_i(character(int(_)) for _ in ip.split('.'))
        elif integer:
            self.path_info = concat_bytes_i(character((integer >> offset) & 0xFF) for offset in [24, 16, 8, 0])
        else:
            self.path_info = b''
        # sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

    def __eq__(self, other):
        return self.path_info == other.path_info

    def __neq__(self, other):
        return self.path_info != other.path_info

    def __lt__(self, other):
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __len__(self):
        return len(self.path_info)

    def json(self):
        if self.path_info:
            return '"path-information": "%s"' % '.'.join([str(ordinal(_)) for _ in self.path_info])
        return ''

    def __repr__(self):
        if self.path_info:
            return ' path-information %s' % '.'.join([str(ordinal(_)) for _ in self.path_info])
        return ''

    def pack(self):
        if self.path_info:
            return self.path_info
        return b'\x00\x00\x00\x00'


PathInfo.NOPATH = PathInfo()
