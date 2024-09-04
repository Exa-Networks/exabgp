# encoding: utf-8
"""
nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message import OUT
from exabgp.bgp.message.notification import Notify

from exabgp.logger import Logger
from exabgp.logger import LazyNLRI


class NLRI(Family):
    __slots__ = ['action']

    EOR = False

    registered_nlri = dict()
    registered_families = [(AFI.ipv4, SAFI.multicast)]
    logger = None

    def __init__(self, afi, safi, action=OUT.UNSET):
        Family.__init__(self, afi, safi)
        self.action = action

    def __hash__(self):
        return hash("%s:%s:%s" % (self.afi, self.safi, self.pack_nlri()))

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

    def _index(self):
        return b'%02x%02x' % (self.afi, self.safi)

    def index(self):
        return self._index() + self.pack_nlri()

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
                    cls.registered_nlri['%s/%s' % new] = klass
                else:
                    raise RuntimeError('Tried to register %s/%s twice' % new)
            else:
                # python has a bug and does not allow %ld/%ld (pypy does)
                cls.registered_nlri['%s/%s' % new] = klass
                cls.registered_families.append(new)
            return klass

        return register_nlri

    @staticmethod
    def known_families():
        # we do not want to take the risk of the caller modifying the list by accident
        # it can not be a generator
        return list(NLRI.registered_families)

    @classmethod
    def unpack_nlri(cls, afi, safi, data, action, addpath):
        if not cls.logger:
            cls.logger = Logger()

        a, s = AFI.create(afi), SAFI.create(safi)
        cls.logger.debug(LazyNLRI(a, s, addpath, data), 'parser')

        key = '%s/%s' % (a, s)
        if key in cls.registered_nlri:
            return cls.registered_nlri[key].unpack_nlri(a, s, data, action, addpath)
        raise Notify(3, 0, 'trying to decode unknown family %s/%s' % (a, s))
