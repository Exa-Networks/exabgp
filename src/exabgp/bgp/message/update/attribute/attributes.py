"""attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json

from struct import unpack

from exabgp.environment import getenv

from exabgp.bgp.message.open.asn import AS_TRANS

from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.attribute import TreatAsWithdraw
from exabgp.bgp.message.update.attribute.attribute import Discard
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import SEQUENCE
from exabgp.bgp.message.update.attribute.aspath import SET
from exabgp.bgp.message.update.attribute.aspath import CONFED_SEQUENCE
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.localpref import LocalPreference

# For bagpipe
from exabgp.bgp.message.update.attribute.community import Communities

from exabgp.bgp.message.notification import Notify

from exabgp.logger import log
from exabgp.logger import lazyattribute


class _NOTHING:
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


def _is_json_number(value):
    """Whether this rendering is already a JSON number and must not be quoted

    Deliberately not json.loads(): it accepts NaN, Infinity and -Infinity, none
    of which are JSON per RFC 8259, and it accepts true, which an isinstance
    check against int does not reject because bool is a subclass of int. Any of
    those emitted unquoted is a line a strict consumer refuses.

    A decimal integer, optionally negative, with no redundant leading zero. That
    is what the attributes taking this branch render, and anything else is safer
    quoted than guessed at.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    digits = text[1:] if text[0] == '-' else text
    if not digits.isdigit():
        return False
    return digits == '0' or digits[0] != '0'


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
        # RFC 7606 sections 7.8, 7.14 and 7.15 give a malformed Community, Extended
        # Community and IPv6 Address Specific Extended Community the same answer:
        # treat-as-withdraw, not a session reset.  The three decoders raise Notify(3, 1)
        # for a length which is not a whole number of communities, and without the code
        # listed here that Notify walks out of parse() and drops the adjacency over one
        # badly encoded optional transitive attribute forwarded from several hops away,
        # which is the failure RFC 7606 was written to remove.  LARGE_COMMUNITY has been
        # in this tuple since it was added, so the three below were drift, not a decision.
        Attribute.CODE.COMMUNITY,
        Attribute.CODE.EXTENDED_COMMUNITY,
        Attribute.CODE.IPV6_EXTENDED_COMMUNITY,
        Attribute.CODE.LARGE_COMMUNITY,
    )

    DISCARD = (
        Attribute.CODE.ATOMIC_AGGREGATE,
        Attribute.CODE.AGGREGATOR,
        # RFC 7752 section 5.3 and RFC 9552 section 7.2.1: a malformed BGP-LS
        # attribute costs the attribute, not the peering
        Attribute.CODE.BGP_LS,
        # RFC 8669 section 6: a BGP Prefix-SID which is not valid MUST be considered
        # malformed and the RFC 7606 Attribute Discard action applied.  Discard rather
        # than treat-as-withdraw because what is lost is the label information, not the
        # reachability the route carries.  Same shape as BGP_LS above.
        Attribute.CODE.BGP_PREFIX_SID,
    )

    MANDATORY = (Attribute.CODE.ORIGIN, Attribute.CODE.AS_PATH, Attribute.CODE.LOCAL_PREF)

    NO_DUPLICATE = (
        Attribute.CODE.MP_REACH_NLRI,
        Attribute.CODE.MP_UNREACH_NLRI,
    )

    VALID_ZERO = (
        Attribute.CODE.ATOMIC_AGGREGATE,
        Attribute.CODE.AS_PATH,
        # Not because an empty Prefix-SID is valid: RFC 8669 section 6 counts "not
        # meeting the minimum attribute length requirement" as malformed, and asks for
        # Attribute Discard.  The generic zero-length rule below produces
        # treat-as-withdraw, which is the wrong one of the two answers, and honouring
        # DISCARD inside that rule instead would silently flip AGGREGATOR and AS4_PATH
        # too.  So the zero length reaches PrefixSid.unpack, which refuses it with a
        # Notify, and DISCARD above turns that into the action the section names.
        Attribute.CODE.BGP_PREFIX_SID,
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
        Attribute.CODE.AS_PATH: ('list', '', 'as-path', '%s', '%s'),
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
        Attribute.CODE.IPV6_EXTENDED_COMMUNITY: ('list', '', 'extended-community-ipv6', '%s', '%s'),
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
                yield ' attribute [ 0x{:02X} 0x{:02X} {} ]'.format(code, attribute.FLAG, str(attribute))
                continue

            if attribute.GENERIC:
                yield ' attribute [ 0x{:02X} 0x{:02X} {} ]'.format(code, attribute.FLAG, str(attribute))
                continue

            how, _, name, presentation, _ = self.representation[code]
            if how == 'boolean':
                yield ' {}'.format(name)
            elif how == 'list':
                yield ' {} {}'.format(name, presentation % str(attribute))
            elif how == 'multiple':
                yield ' {} {}'.format(name[0], presentation % str(attribute))
            else:
                yield ' {} {}'.format(name, presentation % str(attribute))

    def _generate_dict(self):
        for code in sorted(self.keys()):
            if code in Attributes.NO_GENERATION:
                continue

            attribute = self[code]

            if code not in self.representation:
                key = f'attribute-0x{code:02X}-0x{attribute.FLAG:02X}'
                yield key, str(attribute)
                continue

            how, _, name, _, presentation = self.representation[code]
            if how == 'boolean':
                yield name, self.has(code)
            elif how == 'string':
                yield name, str(attribute)
            elif how == 'list':
                yield name, attribute.as_dict()
            elif how == 'integer':
                yield name, int(str(attribute))
            elif how == 'inet':
                yield name, str(attribute)
            # Should never be ran
            else:
                yield name, str(attribute)

    def _generate_json(self):
        for code in sorted(self.keys()):
            # remove the next-hop from the attribute as it is define with the NLRI
            if code in Attributes.NO_GENERATION:
                continue

            attribute = self[code]

            if code not in self.representation:
                yield '"attribute-0x{:02X}-0x{:02X}": {}'.format(code, attribute.FLAG, json.dumps(str(attribute)))
                continue

            how, _, name, _, presentation = self.representation[code]
            if how == 'boolean':
                yield '"{}": {}'.format(name, 'true' if self.has(code) else 'false')
            elif how == 'string':
                yield '"{}": {}'.format(name, json.dumps(presentation % str(attribute)))
            elif how == 'list':
                yield '"{}": {}'.format(name, presentation % attribute.json())
            elif how == 'multiple':
                for n in name:
                    value = attribute.json(n)
                    if value:
                        yield '"{}": {}'.format(n, presentation % value)
            elif how == 'inet':
                yield '"{}": {}'.format(name, json.dumps(presentation % str(attribute)))
            else:
                # this branch was marked 'Should never be ran' and every integer
                # attribute lands in it.  MED and local-preference render as
                # decimal and must stay JSON NUMBERS, because that is what they
                # have always been and consumers do arithmetic on them.  AIGP
                # renders as 0x000000000000000a, which unquoted is not JSON at
                # all and takes the whole line with it, so that one is quoted.
                value = presentation % str(attribute)
                yield '"{}": {}'.format(name, value if _is_json_number(value) else json.dumps(value))

    def __init__(self):
        dict.__init__(self)
        # cached representation of the object
        self._str = ''
        self._idx = ''
        self._json = ''
        self._dict = {}
        # The parsed attributes have no mp routes and/or those are last
        self.cacheable = True

        # XXX: FIXME: surely not the best place for this
        Attribute.caching = getenv().cache.attributes

    def has(self, k):
        return k in self

    def add(self, attribute, _=None):
        # we return None as attribute if the unpack code must not generate them
        if attribute is None:
            return

        if attribute.ID in self:
            if attribute.ID != Attribute.CODE.EXTENDED_COMMUNITY:
                # attempting to add duplicate attribute when not allowed
                return

            self._str = ''
            self._json = ''
            self._dict = {}

            for community in attribute.communities:
                self[attribute.ID].add(community)
            return

        self._str = ''
        self._json = ''
        self._dict = {}

        self[attribute.ID] = attribute

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
            Attribute.CODE.AS_PATH: lambda left, right: (
                ASPath([])
                if left == right
                else ASPath(
                    [
                        SEQUENCE(
                            [
                                local_asn,
                            ],
                        ),
                    ],
                )
            ),
            Attribute.CODE.LOCAL_PREF: lambda left, right: LocalPreference(100) if left == right else NOTHING,
        }

        skip = {
            Attribute.CODE.NEXT_HOP: lambda left, right, nh: nh.ipv4() is not True,
            Attribute.CODE.LOCAL_PREF: lambda left, right, nh: left != right,
        }

        keys = list(self)
        # `with_default` chooses whether the three defaults above are synthesised when they are
        # absent, not whether anything is encoded at all.  The brackets matter: a conditional
        # expression binds looser than `+`, so `keys + list(default) if with_default else []`
        # made the whole concatenation the true branch and `with_default=False` return b''.
        alls = set(keys + (list(default) if with_default else []))

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

    def as_dict(self):
        if not self._dict:
            self._dict = dict(self._generate_dict())
        return self._dict

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
            nexthop = str(self.get(Attribute.CODE.NEXT_HOP, 'missing'))
            self._idx = '{} next-hop {}'.format(idx, nexthop) if nexthop else idx
        return self._idx

    @classmethod
    def unpack(cls, data, direction, negotiated):
        if cls.cached and data == cls.previous:
            return cls.cached

        attributes = cls().parse(data, direction, negotiated)

        if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in attributes:
            return attributes

        attributes.reconcile_four_octet_as()

        if Attribute.CODE.MP_REACH_NLRI not in attributes and Attribute.CODE.MP_UNREACH_NLRI not in attributes:
            cls.previous = data
            cls.cached = attributes
        else:
            cls.previous = ''
            cls.cached = None

        return attributes

    @staticmethod
    def flag_attribute_content(data):
        flag = Attribute.Flag(data[0])
        attr = Attribute.CODE(data[1])

        if flag & Attribute.Flag.EXTENDED_LENGTH:
            length = unpack('!H', data[2:4])[0]
            return flag, attr, data[4 : length + 4]
        length = data[2]
        return flag, attr, data[3 : length + 3]

    def parse(self, data, direction, negotiated):
        # RFC 4271 4.3 bounds the attribute section by the message length alone, so a peer may
        # legitimately put hundreds of small attributes in one UPDATE.  This used to tail-call
        # itself once per attribute, and CPython does not eliminate a tail call: 996 three byte
        # attributes, a 3015 byte UPDATE well inside the 4096 limit and every attribute in it
        # individually well formed, raised RecursionError.  reactor/protocol.py catches it as
        # an unspecified Exception and answers Notify(1, 0), so the peer was told its UPDATE
        # had a malformed header, which is not what was wrong, and the session was reset.
        # In the reactor the ceiling is lower still, because the protocol and loop frames are
        # already on the stack when this is entered.
        while data:
            left = self._parse_one(data, direction, negotiated)
            if left is None:
                break
            # The header is consumed before the value is sliced off, so an attribute always
            # costs at least its three or four header octets and this cannot fire today.  It
            # is a guard rather than an assert because the bytes are the peer's: a loop over
            # peer-controlled input which stops shrinking it does not end, and `python -O`
            # removes an assert.
            if len(left) >= len(data):
                self.add(TreatAsWithdraw())
                break
            data = left
        return self

    def _parse_one(self, data, direction, negotiated):
        """Read one attribute off the front, returning what is left, or None to stop."""
        try:
            # We do not care if the attribute are transitive or not as we do not redistribute
            flag = Attribute.Flag(data[0])
            aid = Attribute.CODE(data[1])
        except IndexError:
            self.add(TreatAsWithdraw())
            return None

        try:
            offset = 3
            length = data[2]

            if flag & Attribute.Flag.EXTENDED_LENGTH:
                offset = 4
                length = (length << 8) + data[3]
        except IndexError:
            self.add(TreatAsWithdraw(aid))
            return None

        data = data[offset:]

        # RFC 7606 section 4: an Attribute Length past the end of the attribute section is
        # an error in the framing of the UPDATE, not in one attribute, so the whole UPDATE
        # takes the treat-as-withdraw approach.  Slicing does not raise on an overrun, so
        # without this the attribute was decoded from however many bytes happened to remain
        # and kept as though the peer had sent it: a COMMUNITY declaring twelve bytes with
        # four behind it became the single community those four decoded to, a community set
        # nobody sent.  It also reached NextHop.unpack with an empty buffer, which answers
        # NoNextHop rather than an attribute, and add() then read .ID off it: an
        # AttributeError out of the parser instead of a NOTIFICATION.
        if length > len(data):
            self.add(TreatAsWithdraw())
            return None

        left = data[length:]
        attribute = data[:length]

        log.debug(lazyattribute(flag, aid, length, data[:length]), 'parser')

        # remove the PARTIAL bit before comparaison if the attribute is optional
        if aid in Attribute.attributes_optional:
            flag &= Attribute.Flag.MASK_PARTIAL & 0xFF
            # flag &= ~Attribute.Flag.PARTIAL & 0xFF  # cleaner than above (python use signed integer for ~)

        if aid in self:
            if aid in self.NO_DUPLICATE:
                raise Notify(3, 1, 'multiple attribute for {}'.format(str(Attribute.CODE(aid))))

            log.debug(
                lambda: 'duplicate attribute {} (flag 0x{:02X}, aid 0x{:02X}) skipping'.format(
                    Attribute.CODE.names.get(aid, 'unset'), flag, aid
                ),
                'parser',
            )
            return left

        # handle the attribute if we know it
        if Attribute.registered(aid, flag):
            if length == 0 and aid not in self.VALID_ZERO:
                self.add(TreatAsWithdraw(aid))
                return left

            try:
                decoded = Attribute.unpack(aid, flag, attribute, direction, negotiated)
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
            return left

        # XXX: FIXME: we could use a fallback function here like capability

        # if we know the attribute but the flag is not what the RFC says.
        if aid in Attribute.attributes_known:
            # RFC 7606 5.3 lists "the attribute flags of the attribute are inconsistent
            # with those specified in [RFC4760]" as one of the ways an MP_REACH_NLRI or
            # MP_UNREACH_NLRI is incorrect, and 3 (j) says that when the MP attributes
            # cannot be successfully parsed the session reset approach MUST be followed.
            # Treat-as-withdraw is not available here: the NLRI are inside the attribute
            # the flags stopped us recognising, so there is nothing left to withdraw, and
            # falling through to the "unspecified" branch below made the routes it carried
            # vanish with no withdrawal and no NOTIFICATION.  Subcode 9, Optional Attribute
            # Error, because RFC 4760 section 7 names it for a session ended over an
            # incorrect MP attribute, and it is what mprnlri.py and mpurnlri.py now raise
            # for every MP attribute they refuse.
            if aid in (Attribute.CODE.MP_REACH_NLRI, Attribute.CODE.MP_UNREACH_NLRI):
                raise Notify(
                    3,
                    9,
                    'invalid flag 0x{:02X} for {}, RFC 4760 makes it optional non-transitive'.format(
                        flag, Attribute.CODE.names.get(aid, 'unset')
                    ),
                )
            if aid in self.TREAT_AS_WITHDRAW:
                log.debug(
                    lambda: 'invalid flag for attribute {} (flag 0x{:02X}, aid 0x{:02X}) treat as withdraw'.format(
                        Attribute.CODE.names.get(aid, 'unset'), flag, aid
                    ),
                    'parser',
                )
                self.add(TreatAsWithdraw())
            if aid in self.DISCARD:
                log.debug(
                    lambda: 'invalid flag for attribute {} (flag 0x{:02X}, aid 0x{:02X}) discard'.format(
                        Attribute.CODE.names.get(aid, 'unset'), flag, aid
                    ),
                    'parser',
                )
                return left
            # XXX: Check if we are missing any
            log.debug(
                lambda: (
                    'invalid flag for attribute {} (flag 0x{:02X}, aid 0x{:02X}) unspecified (should not happen)'.format(
                        Attribute.CODE.names.get(aid, 'unset'), flag, aid
                    )
                ),
                'parser',
            )
            return left

        # it is an unknown transitive attribute we need to pass on
        if flag & Attribute.Flag.TRANSITIVE:
            log.debug(lambda: 'unknown transitive attribute (flag 0x{:02X}, aid 0x{:02X})'.format(flag, aid), 'parser')
            try:
                decoded = GenericAttribute(aid, flag | Attribute.Flag.PARTIAL, attribute)
            except IndexError:
                decoded = TreatAsWithdraw(aid)
            self.add(decoded, attribute)
            return left

        # it is an unknown non-transitive attribute we can ignore.
        log.debug(
            lambda: 'ignoring unknown non-transitive attribute (flag 0x{:02X}, aid 0x{:02X})'.format(flag, aid),
            'parser',
        )
        return left

    def reconcile_four_octet_as(self):
        """RFC 6793 4.2.3: settle the AS4_ attributes an OLD speaker sent beside the real ones.

        The aggregator rules come first because the AGGREGATOR decides whether the AS4_PATH is
        looked at at all, and only then is the path reconstructed.  Nothing used to read the
        AGGREGATOR when merging, so neither rule existed.
        """
        aggregator = self.get(Attribute.CODE.AGGREGATOR, None)
        aggregator4 = self.get(Attribute.CODE.AS4_AGGREGATOR, None)

        if aggregator is not None and aggregator4 is not None:
            assert isinstance(aggregator, Aggregator), 'the AGGREGATOR did not decode to an Aggregator'
            if aggregator.asn != AS_TRANS:
                # An aggregating AS which is a real number was not written by a speaker
                # translating a four octet one, so both AS4_ attributes are noise: the
                # AGGREGATOR is the aggregating node and the AS_PATH is the path.
                self.pop(Attribute.CODE.AS4_AGGREGATOR, None)
                self.pop(Attribute.CODE.AS4_PATH, None)
                return
            # AS_TRANS is a placeholder, not an Autonomous System.  Leaving the AGGREGATOR in
            # told a consumer of the JSON that AS 23456 aggregated the route; the
            # AS4_AGGREGATOR beside it holds the AS number which did.
            self.pop(Attribute.CODE.AGGREGATOR, None)

        if Attribute.CODE.AS_PATH in self and Attribute.CODE.AS4_PATH in self:
            self.merge_attributes()

    def merge_attributes(self):
        as2path = self[Attribute.CODE.AS_PATH]
        as4path = self[Attribute.CODE.AS4_PATH]
        self.remove(Attribute.CODE.AS_PATH)
        self.remove(Attribute.CODE.AS4_PATH)

        # this key is unique as index length is a two header, plus a number of ASN of size 2 or 4
        # so adding the: make the length odd and unique
        key = '{}:{}'.format(as2path.index, as4path.index)

        # found a cache copy
        cached = Attribute.cache.get(Attribute.CODE.AS_PATH, {}).get(key, None)
        if cached:
            self.add(cached, key)
            return

        segments = self._reconstruct_as_path(as2path, as4path)
        # The reconstruction recovers four octet AS numbers on a two octet wire session, so
        # the index is packed as four octet.  ASPath.pack re-translates to AS_TRANS and a
        # fresh AS4_PATH if this route is later advertised to another old speaker.
        packed = b''.join(ASPath._segment(segment.ID, segment, True) for segment in segments)
        self.add(ASPath(segments, packed), key)

    @staticmethod
    def _as_number_count(segments):
        """How many AS numbers a path holds, by the rule of RFC 4271 section 9.1.2.2.

        An AS_SET counts as one whatever it holds, and a confederation segment counts as
        none (RFC 5065 section 5.3).  RFC 6793 4.2.3 leans on this count twice, so the
        reconstruction has to use it rather than a flat count of members.
        """
        total = 0
        for segment in segments:
            if isinstance(segment, SEQUENCE):
                total += len(segment)
            elif isinstance(segment, SET):
                total += 1
        return total

    @classmethod
    def _leading_as_numbers(cls, segments, wanted):
        """The leading part of a path holding `wanted` AS numbers, cutting a segment if it must.

        RFC 6793 4.2.3 takes "as many AS numbers and path segments as necessary from the
        leading part of the AS_PATH", so a sequence which overshoots is cut rather than
        dropped whole, and a confederation segment comes along without paying for itself.
        """
        leading = []
        for segment in segments:
            if wanted <= 0:
                break
            if isinstance(segment, SEQUENCE) and len(segment) > wanted:
                leading.append(SEQUENCE(segment[:wanted]))
                break
            leading.append(segment)
            wanted -= cls._as_number_count((segment,))
        return leading

    @staticmethod
    def _coalesce_segments(segments):
        """Join neighbouring sequences, so the join shows as one segment rather than a seam.

        Only sequences: two adjacent AS_SETs count as two AS numbers and one holding both
        members counts as one, so merging those would change the length of the path.
        """
        joined = []
        for segment in segments:
            previous = joined[-1] if joined else None
            if isinstance(segment, SEQUENCE) and isinstance(previous, SEQUENCE):
                joined[-1] = SEQUENCE(list(previous) + list(segment))
                continue
            if isinstance(segment, CONFED_SEQUENCE) and isinstance(previous, CONFED_SEQUENCE):
                joined[-1] = CONFED_SEQUENCE(list(previous) + list(segment))
                continue
            joined.append(segment)
        return joined

    @classmethod
    def _reconstruct_as_path(cls, as2path, as4path):
        """RFC 6793 4.2.3, which obsoletes the RFC 4893 this used to cite.  Two rules.

        When the AS_PATH holds fewer AS numbers than the AS4_PATH the AS4_PATH is ignored
        and the AS_PATH is the answer.  Otherwise the leading part of the AS_PATH is
        prepended to the AS4_PATH so the result holds as many AS numbers as the AS_PATH did.

        This used to read `as_seq` and `as_set`, one list per segment kind, which ASPath has
        not had since it was refactored to hold a single `aspath` list of path segments: the
        merge raised AttributeError on the ordinary UPDATE which triggers it.  Rewritten on
        the segment list, and counting over the whole path rather than one segment kind at a
        time, which is what the sentence asks for: an AS4_PATH whose only segment is a set
        used to be matched against an AS_PATH with no set, contribute nothing, and leave in
        place the AS_TRANS it had been sent to replace.
        """
        segments2 = as2path.aspath
        segments4 = as4path.aspath
        count2 = cls._as_number_count(segments2)
        count4 = cls._as_number_count(segments4)

        if count2 < count4:
            return list(segments2)

        return cls._coalesce_segments(cls._leading_as_numbers(segments2, count2 - count4) + list(segments4))

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
            for key in set(self.keys()).union(set(other.keys())):
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
