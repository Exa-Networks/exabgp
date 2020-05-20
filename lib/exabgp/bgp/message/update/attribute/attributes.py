# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import unpack

from exabgp.configuration.environment import environment

from exabgp.util import ordinal
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.attribute import TreatAsWithdraw
from exabgp.bgp.message.update.attribute.attribute import Discard
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.localpref import LocalPreference

# For bagpipe
from exabgp.bgp.message.update.attribute.community import Communities

from exabgp.bgp.message.notification import Notify

from exabgp.util import ordinal

from exabgp.logger import Logger
from exabgp.logger import LazyAttribute

from exabgp.vendoring import six


class _NOTHING(object):
    def pack(self, _=None):
        return b''


NOTHING = _NOTHING()


# =================================================================== Attributes
#

# 0                   1
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  Attr. Flags  |Attr. Type Code|
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class Attributes(dict):
    INTERNAL = (
        Attribute.CODE.INTERNAL_SPLIT,
        Attribute.CODE.INTERNAL_WATCHDOG,
        Attribute.CODE.INTERNAL_NAME,
        Attribute.CODE.INTERNAL_WITHDRAW,
        # Attribute.CODE.INTERNAL_DISCARD,
        # Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW,
    )

    NO_GENERATION = (Attribute.CODE.NEXT_HOP,) + INTERNAL

    TREAT_AS_WITHDRAW = (
        Attribute.CODE.ORIGIN,
        Attribute.CODE.AS_PATH,
        Attribute.CODE.NEXT_HOP,
        Attribute.CODE.MED,
        Attribute.CODE.LOCAL_PREF,
        Attribute.CODE.LARGE_COMMUNITY,
    )

    DISCARD = (
        Attribute.CODE.ATOMIC_AGGREGATE,
        Attribute.CODE.AGGREGATOR,
    )

    MANDATORY = (Attribute.CODE.ORIGIN, Attribute.CODE.AS_PATH, Attribute.CODE.LOCAL_PREF)

    NO_DUPLICATE = (
        Attribute.CODE.MP_REACH_NLRI,
        Attribute.CODE.MP_UNREACH_NLRI,
    )

    VALID_ZERO = (
        Attribute.CODE.ATOMIC_AGGREGATE,
        Attribute.CODE.AS_PATH,
    )

    # A cache of parsed attributes
    cache = {}

    # The previously parsed Attributes
    cached = None
    # previously parsed attribute, from which cached was made of
    previous = ''

    representation = {
        # key:  (how, default, name, text_presentation, json_presentation),
        Attribute.CODE.ORIGIN: ('string', '', 'origin', '%s', '%s'),
        Attribute.CODE.AS_PATH: (
            'multiple',
            '',
            ('as-path', 'as-set', 'confederation-path', 'confederation-set'),
            '%s',
            '%s',
        ),
        Attribute.CODE.NEXT_HOP: ('string', '', 'next-hop', '%s', '%s'),
        Attribute.CODE.MED: ('integer', '', 'med', '%s', '%s'),
        Attribute.CODE.LOCAL_PREF: ('integer', '', 'local-preference', '%s', '%s'),
        Attribute.CODE.ATOMIC_AGGREGATE: ('boolean', '', 'atomic-aggregate', '%s', '%s'),
        Attribute.CODE.AGGREGATOR: ('string', '', 'aggregator', '( %s )', '%s'),
        Attribute.CODE.AS4_AGGREGATOR: ('string', '', 'aggregator', '( %s )', '%s'),
        Attribute.CODE.COMMUNITY: ('list', '', 'community', '%s', '%s'),
        Attribute.CODE.LARGE_COMMUNITY: ('list', '', 'large-community', '%s', '%s'),
        Attribute.CODE.ORIGINATOR_ID: ('inet', '', 'originator-id', '%s', '%s'),
        Attribute.CODE.CLUSTER_LIST: ('list', '', 'cluster-list', '%s', '%s'),
        Attribute.CODE.EXTENDED_COMMUNITY: ('list', '', 'extended-community', '%s', '%s'),
        Attribute.CODE.PMSI_TUNNEL: ('string', '', 'pmsi', '%s', '%s'),
        Attribute.CODE.AIGP: ('integer', '', 'aigp', '%s', '%s'),
        Attribute.CODE.BGP_LS: ('list', '', 'bgp-ls', '%s', '%s'),
        Attribute.CODE.BGP_PREFIX_SID: ('list', '', 'bgp-prefix-sid', '%s', '%s'),
        Attribute.CODE.INTERNAL_NAME: ('string', '', 'name', '%s', '%s'),
        Attribute.CODE.INTERNAL_DISCARD: ('string', '', 'error', '%s', '%s'),
        Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW: ('string', '', 'error', '%s', '%s'),
    }

    def _generate_text(self):
        for code in sorted(self.keys()):
            # XXX: FIXME: really we should have a INTERNAL attribute in the classes
            if code in Attributes.NO_GENERATION:
                continue

            attribute = self[code]

            if code not in self.representation:
                yield ' attribute [ 0x%02X 0x%02X %s ]' % (code, attribute.FLAG, str(attribute))
                continue

            if attribute.GENERIC:
                yield ' attribute [ 0x%02X 0x%02X %s ]' % (code, attribute.FLAG, str(attribute))
                continue

            how, _, name, presentation, _ = self.representation[code]
            if how == 'boolean':
                yield ' %s' % name
            elif how == 'list':
                yield ' %s %s' % (name, presentation % str(attribute))
            elif how == 'multiple':
                yield ' %s %s' % (name[0], presentation % str(attribute))
            else:
                yield ' %s %s' % (name, presentation % str(attribute))

    def _generate_json(self):
        for code in sorted(self.keys()):
            # remove the next-hop from the attribute as it is define with the NLRI
            if code in Attributes.NO_GENERATION:
                continue

            attribute = self[code]

            if code not in self.representation:
                yield '"attribute-0x%02X-0x%02X": "%s"' % (code, attribute.FLAG, str(attribute))
                continue

            how, _, name, _, presentation = self.representation[code]
            if how == 'boolean':
                yield '"%s": %s' % (name, 'true' if self.has(code) else 'false')
            elif how == 'string':
                yield '"%s": "%s"' % (name, presentation % str(attribute))
            elif how == 'list':
                yield '"%s": %s' % (name, presentation % attribute.json())
            elif how == 'multiple':
                for n in name:
                    value = attribute.json(n)
                    if value:
                        yield '"%s": %s' % (n, presentation % value)
            elif how == 'inet':
                yield '"%s": "%s"' % (name, presentation % str(attribute))
            # Should never be ran
            else:
                yield '"%s": %s' % (name, presentation % str(attribute))

    def __init__(self):
        dict.__init__(self)
        # cached representation of the object
        self._str = ''
        self._idx = ''
        self._json = ''
        # The parsed attributes have no mp routes and/or those are last
        self.cacheable = True

        # XXX: FIXME: surely not the best place for this
        Attribute.caching = environment.settings().cache.attributes

    def has(self, k):
        return k in self

    def add(self, attribute, _=None):
        # we return None as attribute if the unpack code must not generate them
        if attribute is None:
            return
        if attribute.ID in self:
            return

        self._str = ''
        self._json = ''

        self[attribute.ID] = attribute

    # This is as when we generate flow spec we can have multiple keywords
    # which are all adding information in the extended-community
    def add_and_merge(self, attribute):
        if attribute.ID not in self:
            self.add(attribute)
            return

        if attribute.ID == Attribute.CODE.EXTENDED_COMMUNITY:
            for community in attribute.communities:
                self[attribute.ID].add(community)

    def remove(self, attrid):
        self.pop(attrid)

    def watchdog(self):
        return self.pop(Attribute.CODE.INTERNAL_WATCHDOG, None)

    def withdraw(self):
        return self.pop(Attribute.CODE.INTERNAL_WITHDRAW, None) is not None

    def pack(self, negotiated, with_default=True):
        local_asn = negotiated.local_as
        peer_asn = negotiated.peer_as

        message = b''

        default = {
            Attribute.CODE.ORIGIN: lambda left, right: Origin(Origin.IGP),
            Attribute.CODE.AS_PATH: lambda left, right: ASPath([], []) if left == right else ASPath([local_asn,], []),
            Attribute.CODE.LOCAL_PREF: lambda left, right: LocalPreference(100) if left == right else NOTHING,
        }

        skip = {
            Attribute.CODE.NEXT_HOP: lambda left, right, nh: nh.ipv4() is not True,
            Attribute.CODE.LOCAL_PREF: lambda left, right, nh: left != right,
        }

        keys = list(self)
        alls = set(keys + list(default) if with_default else [])

        for code in sorted(alls):
            if code in Attributes.INTERNAL:
                continue

            if code not in keys and code in default:
                message += default[code](local_asn, peer_asn).pack(negotiated)
                continue

            attribute = self[code]

            if code in skip and skip[code](local_asn, peer_asn, attribute):
                continue

            message += attribute.pack(negotiated)

        return message

    def json(self):
        if not self._json:
            self._json = ', '.join(self._generate_json())
        return self._json

    def __repr__(self):
        if not self._str:
            self._str = ''.join(self._generate_text())
        return self._str

    def index(self):
        # XXX: something a little bit smaller memory wise ?
        if not self._idx:
            idx = ''.join(self._generate_text())
            nexthop = str(self.get(Attribute.CODE.NEXT_HOP, ''))
            self._idx = '%s next-hop %s' % (idx, nexthop) if nexthop else idx
        return self._idx

    @classmethod
    def unpack(cls, data, negotiated):
        if cls.cached and data == cls.previous:
            return cls.cached

        attributes = cls().parse(data, negotiated)

        if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in attributes:
            return attributes

        if Attribute.CODE.AS_PATH in attributes and Attribute.CODE.AS4_PATH in attributes:
            attributes.merge_attributes()

        if Attribute.CODE.MP_REACH_NLRI not in attributes and Attribute.CODE.MP_UNREACH_NLRI not in attributes:
            cls.previous = data
            cls.cached = attributes
        else:
            cls.previous = ''
            cls.cached = None

        return attributes

    @staticmethod
    def flag_attribute_content(data):
        flag = Attribute.Flag(ordinal(data[0]))
        attr = Attribute.CODE(ordinal(data[1]))

        if flag & Attribute.Flag.EXTENDED_LENGTH:
            length = unpack('!H', data[2:4])[0]
            return flag, attr, data[4 : length + 4]
        else:
            length = ordinal(data[2])
            return flag, attr, data[3 : length + 3]

    def parse(self, data, negotiated):
        if not data:
            return self

        try:
            # We do not care if the attribute are transitive or not as we do not redistribute
            flag = Attribute.Flag(ordinal(data[0]))
            aid = Attribute.CODE(ordinal(data[1]))
        except IndexError:
            self.add(TreatAsWithdraw())
            return self

        try:
            offset = 3
            length = ordinal(data[2])

            if flag & Attribute.Flag.EXTENDED_LENGTH:
                offset = 4
                length = (length << 8) + ordinal(data[3])
        except IndexError:
            self.add(TreatAsWithdraw(aid))
            return self

        data = data[offset:]
        left = data[length:]
        attribute = data[:length]

        logger = Logger()
        logger.debug(LazyAttribute(flag, aid, length, data[:length]), 'parser')

        # remove the PARTIAL bit before comparaison if the attribute is optional
        if aid in Attribute.attributes_optional:
            flag &= Attribute.Flag.MASK_PARTIAL & 0xFF
            # flag &= ~Attribute.Flag.PARTIAL & 0xFF  # cleaner than above (python use signed integer for ~)

        if aid in self:
            if aid in self.NO_DUPLICATE:
                raise Notify(3, 1, 'multiple attribute for %s' % str(Attribute.CODE(attribute.ID)))

            logger.debug(
                'duplicate attribute %s (flag 0x%02X, aid 0x%02X) skipping'
                % (Attribute.CODE.names.get(aid, 'unset'), flag, aid),
                'parser',
            )
            return self.parse(left, negotiated)

        # handle the attribute if we know it
        if Attribute.registered(aid, flag):
            if length == 0 and aid not in self.VALID_ZERO:
                self.add(TreatAsWithdraw(aid))
                return self.parse(left, negotiated)

            try:
                decoded = Attribute.unpack(aid, flag, attribute, negotiated)
            except IndexError as exc:
                if aid in self.TREAT_AS_WITHDRAW:
                    decoded = TreatAsWithdraw(aid)
                else:
                    raise exc
            except Notify as exc:
                if aid in self.TREAT_AS_WITHDRAW:
                    decoded = TreatAsWithdraw()
                elif aid in self.DISCARD:
                    decoded = Discard()
                else:
                    raise exc
            self.add(decoded)
            return self.parse(left, negotiated)

        # XXX: FIXME: we could use a fallback function here like capability

        # if we know the attribute but the flag is not what the RFC says.
        if aid in Attribute.attributes_known:
            if aid in self.TREAT_AS_WITHDRAW:
                logger.debug(
                    'invalid flag for attribute %s (flag 0x%02X, aid 0x%02X) treat as withdraw'
                    % (Attribute.CODE.names.get(aid, 'unset'), flag, aid),
                    'parser',
                )
                self.add(TreatAsWithdraw())
            if aid in self.DISCARD:
                logger.debug(
                    'invalid flag for attribute %s (flag 0x%02X, aid 0x%02X) discard'
                    % (Attribute.CODE.names.get(aid, 'unset'), flag, aid),
                    'parser',
                )
                return self.parse(left, negotiated)
            # XXX: Check if we are missing any
            logger.debug(
                'invalid flag for attribute %s (flag 0x%02X, aid 0x%02X) unspecified (should not happen)'
                % (Attribute.CODE.names.get(aid, 'unset'), flag, aid),
                'parser',
            )
            return self.parse(left, negotiated)

        # it is an unknown transitive attribute we need to pass on
        if flag & Attribute.Flag.TRANSITIVE:
            logger.debug('unknown transitive attribute (flag 0x%02X, aid 0x%02X)' % (flag, aid), 'parser')
            try:
                decoded = GenericAttribute(aid, flag | Attribute.Flag.PARTIAL, attribute)
            except IndexError:
                decoded = TreatAsWithdraw(aid)
            self.add(decoded, attribute)
            return self.parse(left, negotiated)

        # it is an unknown non-transitive attribute we can ignore.
        logger.debug('ignoring unknown non-transitive attribute (flag 0x%02X, aid 0x%02X)' % (flag, aid), 'parser')
        return self.parse(left, negotiated)

    def merge_attributes(self):
        as2path = self[Attribute.CODE.AS_PATH]
        as4path = self[Attribute.CODE.AS4_PATH]
        self.remove(Attribute.CODE.AS_PATH)
        self.remove(Attribute.CODE.AS4_PATH)

        # this key is unique as index length is a two header, plus a number of ASN of size 2 or 4
        # so adding the: make the length odd and unique
        key = "%s:%s" % (as2path.index, as4path.index)

        # found a cache copy
        cached = Attribute.cache.get(Attribute.CODE.AS_PATH, {}).get(key, None)
        if cached:
            self.add(cached, key)
            return

        # as_seq = []
        # as_set = []

        len2 = len(as2path.as_seq)
        len4 = len(as4path.as_seq)

        # RFC 4893 section 4.2.3
        if len2 < len4:
            as_seq = as2path.as_seq
        else:
            as_seq = as2path.as_seq[:-len4]
            as_seq.extend(as4path.as_seq)

        len2 = len(as2path.as_set)
        len4 = len(as4path.as_set)

        if len2 < len4:
            as_set = as4path.as_set
        else:
            as_set = as2path.as_set[:-len4]
            as_set.extend(as4path.as_set)

        aspath = ASPath(as_seq, as_set)
        self.add(aspath, key)

    def __hash__(self):
        # FIXME: two routes with distinct nh but other attributes equal
        # will hash to the same value until repr represents the nh (??)
        return hash(repr(self))

    def __eq__(self, other):
        return self.sameValuesAs(other)

    # BaGPipe code ..

    # test that sets of attributes exactly match
    # can't rely on __eq__ for this, because __eq__ relies on Attribute.__eq__ which does not look at attributes values

    def sameValuesAs(self, other):
        # we sort based on packed values since the items do not
        # necessarily implement __cmp__
        def pack_(x):
            return x.pack()

        try:
            for key in set(six.iterkeys(self)).union(set(six.iterkeys(other))):
                if key == Attribute.CODE.MP_REACH_NLRI or key == Attribute.CODE.MP_UNREACH_NLRI:
                    continue

                sval = self[key]
                oval = other[key]

                # In the case where the attribute is Communities or
                # extended communities, we want to compare values independently of their order
                if isinstance(sval, Communities):
                    if not isinstance(oval, Communities):
                        return False

                    sval = sorted(sval, key=pack_)
                    oval = sorted(oval, key=pack_)

                if sval != oval:
                    return False
            return True
        except KeyError:
            return False
