"""bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


# ===================================================================== PathInfo
# RFC draft-ietf-idr-add-paths-09


class PathInfo:
    NOPATH: 'PathInfo | None' = None

    def __init__(self, packed=None, integer=None, ip=None):
        if packed:
            self.path_info = packed
        elif ip:
            self.path_info = b''.join(bytes([int(_)]) for _ in ip.split('.'))
        elif integer:
            self.path_info = b''.join(bytes([(integer >> offset) & 0xFF]) for offset in [24, 16, 8, 0])
        else:
            self.path_info = b''
        # sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

    def __copy__(self):
        """NOPATH is a singleton and index() tests it with `is`

        INET.index(), Label.index() and IPVPN.index() all read

            addpath = b'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack()

        so a copy which mints a new object stops being NOPATH, the index gains
        four zero bytes where it had b'no-pi', and the route is no longer equal
        to itself.  A deepcopied route did not match its original, hashed
        differently and could not be found in a dict keyed on it: the RIB would
        hold the same prefix twice.  A singleton has to copy to itself.
        """
        if self is PathInfo.NOPATH:
            return self
        return PathInfo(packed=self.path_info)

    def __deepcopy__(self, memo=None):
        # copy.deepcopy is the one the RIB actually uses
        if self is PathInfo.NOPATH:
            return self
        return PathInfo(packed=self.path_info)

    def __eq__(self, other):
        if not isinstance(other, PathInfo):
            return NotImplemented
        return self.path_info == other.path_info

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

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
            return '"path-information": "{}"'.format('.'.join([str(_) for _ in self.path_info]))
        return ''

    def __repr__(self):
        if self.path_info:
            return ' path-information {}'.format('.'.join([str(_) for _ in self.path_info]))
        return ''

    def pack(self):
        if self.path_info:
            return self.path_info
        return b'\x00\x00\x00\x00'


PathInfo.NOPATH = PathInfo()
