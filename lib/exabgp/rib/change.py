# encoding: utf-8
"""
change.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


class Source(object):
    UNSET = 0
    CONFIGURATION = 1
    API = 2
    NETWORK = 3


class Change(object):
    SOURCE = Source.UNSET

    __slots__ = ['nlri', 'attributes', '__index']

    @staticmethod
    def family_prefix(family):
        return b'%02x%02x' % family

    def __init__(self, nlri, attributes):
        self.nlri = nlri
        self.attributes = attributes
        # prevent multiple allocation of the index when calling .index()
        # storing the value at __init__ time causes api-attributes.sequence to fail
        # XXX: the NLRI content is half missing !!
        self.__index = ''

    def index(self):
        if not self.__index:
            self.__index = b'%02x%02x' % self.nlri.family() + self.nlri.index()
        return self.__index

    def __eq__(self, other):
        return self.nlri == other.nlri and self.attributes == other.attributes

    def __ne__(self, other):
        return self.nlri != other.nlri or self.attributes != other.attributes

    def __lt__(self, other):
        raise RuntimeError('comparing Change for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing Change for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing Change for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing Change for ordering does not make sense')

    def extensive(self):
        # If you change this you must change as well extensive in Update
        return "%s%s" % (str(self.nlri), str(self.attributes))

    def __repr__(self):
        return self.extensive()

    def feedback(self):
        if self.nlri is not None:
            return self.nlri.feedback(self.nlri.action)
        return 'no check implemented for the family %s %s' % self.nlri.family()


class ConfigurationChange(Change):
    SOURCE = Source.CONFIGURATION


class APIChange(Change):
    SOURCE = Source.API


class NetworkChange(Change):
    SOURCE = Source.NETWORK
