"""How an UPDATE is assembled: the budget a withdrawal is judged on, and RFC 7606 5.1.

Two rules are under test here.

RFC 4271 4.3 makes the Path Attributes field optional and RFC 4760 3 says an UPDATE
carrying MP_UNREACH_NLRI "is not required to carry any other path attributes", so the
room the announcement's attributes leave cannot decide whether a withdrawal is sent.

RFC 7606 5.1: "An UPDATE message MUST NOT contain more than one of the following:
non-empty Withdrawn Routes field, non-empty Network Layer Reachability Information
field, MP_REACH_NLRI attribute, and MP_UNREACH_NLRI attribute."
"""

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attributes, NextHop
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.logger import log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

# The header the reactor puts in front of the body, and the two length fields of RFC 4271 4.3.
HEADER_AND_LENGTHS = 19 + 2 + 2


@pytest.fixture(autouse=True)
def quiet_codec_logging(monkeypatch):
    monkeypatch.setattr(log, 'debug', lambda *args: None)
    monkeypatch.setattr(log, 'critical', lambda *args: None)


def negotiated_session():
    negotiated = Negotiated({'capability': {'aigp': False}})
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv4, SAFI.multicast),
        (AFI.ipv6, SAFI.unicast),
    ]
    return negotiated


def routed_prefix(prefix, action=Action.ANNOUNCE, safi=SAFI.unicast, nexthop=True):
    address, mask = prefix.split('/')
    ip = IP.create(address)
    nlri = INET(ip.afi, safi, action)
    nlri.cidr = CIDR(ip.pack(), int(mask))
    if nexthop:
        nlri.nexthop = IP.create('192.0.2.1' if ip.afi == AFI.ipv4 else '2001:db8::ffff')
    return nlri


def padded_attributes(negotiated, spare):
    """Attributes leaving exactly `spare` octets of an UPDATE for an announcement.

    A negative `spare` is an announcement which cannot be packed at all, which is the
    condition the dropped withdrawals hung off.
    """

    def build(payload):
        attributes = Attributes()
        attributes.add(NextHop('192.0.2.1'))
        # 0xFD is unassigned, optional transitive, so it survives packing untouched.
        attributes.add(GenericAttribute(0xFD, 0xC0, bytes(payload)))
        return attributes

    # The attribute header grows by one octet past 255 of payload, so the size is searched
    # rather than computed.
    for payload in range(2 * negotiated.msg_size):
        attributes = build(payload)
        left = negotiated.msg_size - HEADER_AND_LENGTHS - len(attributes.pack(negotiated, True))
        if left == spare:
            return attributes
    raise AssertionError('no attribute size leaves {} octets of this session'.format(spare))


def carriers(message):
    """Which of RFC 7606 5.1's four NLRI carriers this wire message fills."""
    body = message[19:]
    withdrawn_length = int.from_bytes(body[0:2], 'big')
    attributes_at = 2 + withdrawn_length
    attribute_length = int.from_bytes(body[attributes_at : attributes_at + 2], 'big')
    announced_at = attributes_at + 2 + attribute_length
    attributes = body[attributes_at + 2 : announced_at]

    found = []
    if withdrawn_length:
        found.append('WITHDRAWN')
    if len(body) > announced_at:
        found.append('NLRI')

    offset = 0
    while offset < len(attributes):
        flag = attributes[offset]
        code = attributes[offset + 1]
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            length = int.from_bytes(attributes[offset + 2 : offset + 4], 'big')
            offset += 4
        else:
            length = attributes[offset + 2]
            offset += 3
        offset += length
        if code == Attribute.CODE.MP_REACH_NLRI:
            found.append('MP_REACH')
        if code == Attribute.CODE.MP_UNREACH_NLRI:
            found.append('MP_UNREACH')
    assert offset == len(attributes), 'the path attributes of the message we built do not parse'
    return found


def routes_of(message, negotiated):
    from exabgp.bgp.message.direction import Direction

    return Update.unpack_message(message[19:], Direction.IN, negotiated).nlris


def prefixes(messages, negotiated, action):
    return [
        nlri.cidr.prefix() for message in messages for nlri in routes_of(message, negotiated) if nlri.action == action
    ]


# ============================================== a withdrawal is not sized on the announcement


def test_native_withdrawal_survives_oversized_attributes():
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, -1)
    withdrawal = routed_prefix('10.0.1.0/24', Action.WITHDRAW)
    messages = list(Update([withdrawal], attributes).messages(negotiated))
    assert prefixes(messages, negotiated, Action.WITHDRAW) == ['10.0.1.0/24']


def test_native_withdrawal_survives_attributes_far_past_the_message_size():
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, -200)
    withdrawal = routed_prefix('10.0.1.0/24', Action.WITHDRAW)
    messages = list(Update([withdrawal], attributes).messages(negotiated))
    assert prefixes(messages, negotiated, Action.WITHDRAW) == ['10.0.1.0/24']


def test_oversized_attributes_refuse_the_announcement_and_send_the_withdrawal():
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, -1)
    routes = [routed_prefix('10.0.2.0/24'), routed_prefix('10.0.1.0/24', Action.WITHDRAW)]
    messages = list(Update(routes, attributes).messages(negotiated))
    assert prefixes(messages, negotiated, Action.WITHDRAW) == ['10.0.1.0/24']
    assert prefixes(messages, negotiated, Action.ANNOUNCE) == []


def test_a_native_withdrawal_survives_an_impossible_mp_announcement():
    # The refusal used to return from the method before any pass had run, so an MP family
    # whose attributes did not fit took the IPv4 withdrawals with it.
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, -1)
    routes = [
        routed_prefix('10.0.1.0/24', Action.WITHDRAW),
        routed_prefix('2001:db8::1/128'),
    ]
    messages = list(Update(routes, attributes).messages(negotiated))
    assert prefixes(messages, negotiated, Action.WITHDRAW) == ['10.0.1.0/24']
    assert prefixes(messages, negotiated, Action.ANNOUNCE) == []


def test_an_mp_unreach_only_update_ignores_the_attributes_entirely():
    # RFC 4760 3: an UPDATE carrying MP_UNREACH_NLRI "is not required to carry any other path
    # attributes", and a unicast withdraw-only UPDATE carries none here, so no weight of
    # attributes can stop it.
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, -1)
    withdrawal = routed_prefix('2001:db8::1/128', Action.WITHDRAW, nexthop=False)
    messages = list(Update([withdrawal], attributes).messages(negotiated))
    assert [carriers(message) for message in messages] == [['MP_UNREACH']]
    assert prefixes(messages, negotiated, Action.WITHDRAW) == ['2001:db8::1/128']


def test_an_mp_withdrawal_beside_an_announcement_cannot_escape_oversized_attributes():
    # Recorded rather than fixed.  Once the UPDATE holds an announcement the attributes are
    # packed, and this branch puts them on the MP_UNREACH message too, so there is no budget
    # on which this withdrawal fits.  Dropping them from it is what RFC 4760 3 allows and it
    # would rewrite the attribute field of every recorded MP withdrawal.  What the test holds
    # is that the family is refused rather than answered with a NOTIFICATION.
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, -1)
    routes = [
        routed_prefix('2001:db8::1/128', Action.WITHDRAW, nexthop=False),
        routed_prefix('2001:db8::2/128'),
    ]
    assert list(Update(routes, attributes).messages(negotiated)) == []


def test_withdrawals_are_batched_on_their_own_budget():
    # A withdraw-only UPDATE carries no path attribute, so 300 prefixes fit one message
    # whatever the announcement's attributes weigh.
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, 8)
    withdrawals = [
        routed_prefix('10.{}.{}.0/24'.format(index // 256, index % 256), Action.WITHDRAW) for index in range(300)
    ]
    messages = list(Update(withdrawals, attributes).messages(negotiated))
    assert len(messages) == 1
    assert len(prefixes(messages, negotiated, Action.WITHDRAW)) == 300


def test_a_withdrawal_wider_than_a_message_is_still_refused():
    negotiated = negotiated_session()
    negotiated.msg_size = 25
    withdrawal = routed_prefix('10.0.1.0/24', Action.WITHDRAW)
    assert list(Update([withdrawal], Attributes()).messages(negotiated)) == []


# ============================= our own encoding limit is never a NOTIFICATION to the peer
#
# `msg_size <= 0` in _mp_messages catches the attributes which leave no room at all, and is
# covered above.  A budget which is positive but narrower than one MP attribute went past
# that guard and into MPRNLRI/MPURNLRI.packed_attributes, which raised Notify(6, 0) --
# Cease / Unspecific.  peer.py turns a Notify out of the sending path into a NOTIFICATION on
# the wire, so the peer lost every route of every family because of the size of something WE
# were encoding, and would lose them again on the next session, the offending route still
# being in our RIB.  RFC 4486's Cease subcodes are all administrative; none of them is "we
# could not encode this".


def test_an_mp_announcement_too_wide_for_the_message_is_not_a_notification():
    # 30 octets left: an MP_REACH_NLRI for one IPv6 /128 needs 41 with its attribute header.
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, 30)
    announcement = routed_prefix('2001:db8::1/128')
    assert list(Update([announcement], attributes).messages(negotiated)) == []


def test_an_mp_withdrawal_too_wide_for_the_message_is_not_a_notification():
    # 5 octets left: an MP_UNREACH_NLRI for one IPv6 /128 needs 23.  The announcement beside
    # it is what makes the attributes be packed in full, see _include_defaults.
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, 5)
    routes = [
        routed_prefix('2001:db8::1/128', Action.WITHDRAW, nexthop=False),
        routed_prefix('2001:db8::2/128'),
    ]
    assert list(Update(routes, attributes).messages(negotiated)) == []


def test_an_mp_withdrawal_goes_out_when_only_the_announcement_is_too_wide():
    # 30 octets fit the MP_UNREACH_NLRI's 23 and not the MP_REACH_NLRI's 41.  The Cease was
    # raised from the announcement pass, after the withdrawal had been yielded, so the
    # generator died before the withdrawal reached the wire.
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, 30)
    routes = [
        routed_prefix('2001:db8::1/128', Action.WITHDRAW, nexthop=False),
        routed_prefix('2001:db8::2/128'),
    ]
    messages = list(Update(routes, attributes).messages(negotiated))
    assert [carriers(message) for message in messages] == [['MP_UNREACH']]
    assert prefixes(messages, negotiated, Action.WITHDRAW) == ['2001:db8::1/128']


def test_the_mp_route_which_fits_is_still_sent_beside_the_one_which_does_not():
    # Dropping only the NLRI which cannot be packed, rather than the family, is what the
    # native IPv4 pass does.  The MP_REACH header and its attribute header cost 24 octets, a
    # /32 costs 5 and a /128 costs 17, so a budget of 30 holds the /32 and never the /128.
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, 30)
    routes = [routed_prefix('2001:db8::/32'), routed_prefix('2001:db8::1/128')]
    messages = list(Update(routes, attributes).messages(negotiated))
    assert prefixes(messages, negotiated, Action.ANNOUNCE) == ['2001:db8::/32']


def test_no_mp_message_is_wider_than_the_negotiated_size():
    # The old loop restarted the payload with the NLRI which had just overflowed it already
    # in place, and only measured again on the NLRI after that, so the last attribute it
    # yielded could be wider than the budget.  RFC 4271 4.1 makes the peer answer an UPDATE
    # past the negotiated maximum message size with Bad Message Length.
    negotiated = negotiated_session()
    routes = [
        routed_prefix('2001:db8::/32'),
        routed_prefix('2001:db8::1/128'),
        routed_prefix('2001:db8::2/128'),
    ]
    for spare in range(30, 48):
        attributes = padded_attributes(negotiated, spare)
        for message in Update(routes, attributes).messages(negotiated):
            assert len(message) <= negotiated.msg_size, (spare, len(message))


# ==================================================================== RFC 7606 5.1, one carrier


def test_every_message_fills_a_single_carrier():
    negotiated = negotiated_session()
    attributes = Attributes()
    attributes.add(NextHop('192.0.2.1'))
    routes = [
        routed_prefix('10.0.0.0/24'),
        routed_prefix('10.0.1.0/24', Action.WITHDRAW),
        routed_prefix('2001:db8::/32'),
        routed_prefix('2001:db9::/32', Action.WITHDRAW),
        routed_prefix('239.1.0.0/16', safi=SAFI.multicast),
        routed_prefix('239.2.0.0/16', Action.WITHDRAW, SAFI.multicast),
    ]
    messages = list(Update(routes, attributes).messages(negotiated))
    for message in messages:
        assert len(carriers(message)) == 1, carriers(message)


def test_native_announce_and_withdraw_do_not_share_a_message():
    negotiated = negotiated_session()
    attributes = Attributes()
    attributes.add(NextHop('192.0.2.1'))
    routes = [routed_prefix('10.0.0.0/24'), routed_prefix('10.0.1.0/24', Action.WITHDRAW)]
    messages = list(Update(routes, attributes).messages(negotiated))
    assert [carriers(message) for message in messages] == [['WITHDRAWN'], ['NLRI']]


def test_mp_reach_and_unreach_do_not_share_a_message():
    negotiated = negotiated_session()
    routes = [routed_prefix('2001:db8::1/128', Action.WITHDRAW), routed_prefix('2001:db8::2/128')]
    messages = list(Update(routes, Attributes()).messages(negotiated))
    assert [carriers(message) for message in messages] == [['MP_UNREACH'], ['MP_REACH']]


def test_a_prefix_is_withdrawn_before_it_is_reannounced():
    negotiated = negotiated_session()
    attributes = Attributes()
    attributes.add(NextHop('192.0.2.1'))
    routes = [routed_prefix('10.0.0.0/24'), routed_prefix('10.0.0.0/24', Action.WITHDRAW)]
    messages = list(Update(routes, attributes).messages(negotiated))
    actions = [nlri.action for message in messages for nlri in routes_of(message, negotiated)]
    assert actions == [Action.WITHDRAW, Action.ANNOUNCE]


def test_mp_withdrawal_precedes_the_reannouncement_across_message_boundaries():
    negotiated = negotiated_session()
    announces = [routed_prefix('2001:db8::{:x}/128'.format(index)) for index in range(300)]
    withdrawal = routed_prefix('2001:db8:1::1/128', Action.WITHDRAW)
    messages = list(Update(announces + [withdrawal], Attributes()).messages(negotiated))
    seen = [carriers(message) for message in messages]
    assert seen[0] == ['MP_UNREACH']
    assert all(carrier == ['MP_REACH'] for carrier in seen[1:])


# ======================================================================= nothing else moved


def test_announcement_batching_is_unchanged():
    negotiated = negotiated_session()
    attributes = Attributes()
    attributes.add(NextHop('192.0.2.1'))
    announces = [routed_prefix('10.{}.{}.0/24'.format(index // 256, index % 256)) for index in range(2000)]
    messages = list(Update(announces, attributes).messages(negotiated))
    assert len(messages) == 2
    assert len(prefixes(messages, negotiated, Action.ANNOUNCE)) == 2000


def test_a_suppressed_withdrawal_emits_nothing():
    negotiated = negotiated_session()
    withdrawal = routed_prefix('10.0.1.0/24', Action.WITHDRAW)
    assert list(Update([withdrawal], Attributes()).messages(negotiated, include_withdraw=False)) == []


def test_an_announcement_wider_than_the_attributes_allow_is_still_refused():
    negotiated = negotiated_session()
    attributes = padded_attributes(negotiated, 3)
    announce = routed_prefix('10.0.1.0/24')
    assert list(Update([announce], attributes).messages(negotiated)) == []


# ============================================= the daemon reaches this, which main's RIB does not


def test_the_grouped_rib_yields_an_update_which_used_to_mix_carriers():
    from exabgp.rib.change import Change
    from exabgp.rib.outgoing import OutgoingRIB

    negotiated = negotiated_session()
    negotiated.families = [(AFI.ipv4, SAFI.unicast)]
    attributes = Attributes()
    attributes.add(NextHop('192.0.2.1'))

    rib = OutgoingRIB(True, [(AFI.ipv4, SAFI.unicast)])
    rib.add_to_rib(Change(routed_prefix('10.0.0.0/24'), attributes))
    assert len(list(rib.updates(True))) == 1

    # A withdrawal keeps the attributes of the announcement it cancels, so it lands in the
    # same attribute bucket as an unrelated announcement and the two are grouped.
    rib.del_from_rib(Change(routed_prefix('10.0.0.0/24'), attributes))
    rib.add_to_rib(Change(routed_prefix('10.0.2.0/24'), attributes))
    updates = list(rib.updates(True))
    assert len(updates) == 1
    assert {nlri.action for nlri in updates[0].nlris} == {Action.ANNOUNCE, Action.WITHDRAW}

    for message in updates[0].messages(negotiated):
        assert len(carriers(message)) == 1, carriers(message)
