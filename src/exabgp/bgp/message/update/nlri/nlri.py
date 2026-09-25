"""nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo

from exabgp.logger import log
from exabgp.logger import lazynlri


class NLRI(Family):
    EOR = False

    registered_nlri = dict()
    registered_families = [(AFI.ipv4, SAFI.multicast)]

    def __init__(self, afi, safi, action=Action.UNSET):
        Family.__init__(self, afi, safi)
        self.action = action

    def __hash__(self):
        return hash('{}:{}:{}'.format(self.afi, self.safi, self.pack_nlri()))

    def __eq__(self, other):
        return self.index() == other.index()

    def __ne__(self, other):
        return self.index() != other.index()

    # does not really make sense but allows to get the NLRI in a
    # deterministic order when generating update (Good for testing)

    def __lt__(self, other):
        return self.index() < other.index()

    def __le__(self, other):
        return self == other or self.index() < other.index()

    def __gt__(self, other):
        return self.index() > other.index()

    def __ge__(self, other):
        return self == other or self.index() > other.index()

    def feedback(self, action):
        raise RuntimeError('feedback is not implemented')

    def assign(self, name, value):
        setattr(self, name, value)

    def index(self):
        return Family.index(self) + self.pack_nlri()

    # remove this when code restructure is finished
    def pack(self, negotiated=None):
        return self.pack_nlri(negotiated)

    def pack_nlri(self, negotiated=None):
        raise Exception('unimplemented in NLRI children class')

    @classmethod
    def register(cls, afi, safi, force=False):
        def register_nlri(klass):
            new = (AFI.create(afi), SAFI.create(safi))
            if new in cls.registered_nlri:
                if force:
                    # python has a bug and does not allow %ld/%ld (pypy does)
                    cls.registered_nlri['{}/{}'.format(*new)] = klass
                else:
                    raise RuntimeError('Tried to register {}/{} twice'.format(*new))
            else:
                # python has a bug and does not allow %ld/%ld (pypy does)
                cls.registered_nlri['{}/{}'.format(*new)] = klass
                cls.registered_families.append(new)
            return klass

        return register_nlri

    @staticmethod
    def known_families():
        # we do not want to take the risk of the caller modifying the list by accident
        # it can not be a generator
        return list(NLRI.registered_families)

    @staticmethod
    def consume_path_information(data, addpath):
        """Take the ADD-PATH Path Identifier off the front of an NLRI (RFC 7911 section 3).

        `addpath` is the question "has ADD-PATH been negotiated for this family", not the
        identifier itself.  When the answer is yes the peer has put four bytes in front of
        every NLRI of that family and they have to come off before the NLRI is read.

        This exists because seven families skipped that step and assigned the parameter
        straight into `nlri.addpath`.  They read their first field from the identifier's
        first byte and left four bytes in the buffer, so every NLRI after the first in the
        same UPDATE was read from the wrong offset.
        """
        if not addpath:
            return PathInfo.NOPATH, data
        if len(data) < PathInfo.LENGTH:
            raise Notify(3, 10, 'not enough data to extract the path-information of the NLRI')
        return PathInfo(bytes(data[: PathInfo.LENGTH])), data[PathInfo.LENGTH :]

    @classmethod
    def unpack_nlri(cls, afi, safi, data, action, addpath):
        a, s = AFI.create(afi), SAFI.create(safi)
        log.debug(lazynlri(a, s, addpath, data), 'parser')

        key = '{}/{}'.format(a, s)
        if key in cls.registered_nlri:
            return cls.registered_nlri[key].unpack_nlri(a, s, data, action, addpath)
        raise Notify(3, 0, 'trying to decode unknown family {}/{}'.format(a, s))
