"""RFC 7606 5.1: one NLRI carrier per UPDATE, and what the split must not break.

An UPDATE "MUST NOT contain more than one of the following: non-empty Withdrawn Routes
field, non-empty Network Layer Reachability Information field, MP_REACH_NLRI attribute, and
MP_UNREACH_NLRI attribute."  `UpdateCollection.messages` therefore fills the four carriers
from passes which never share a message, withdrawals first.

That split is the part of the encoder most able to do damage, because it changes what goes
on the wire in a live session, and it was covered by two unit tests and by nothing else: no
recorded capture in `qa/encoding` or `qa/api` is an UPDATE which both announces and
withdraws, so re-recording all 395 of them moved no message count at all.

So this file asserts on the bytes the split produces, on both sides of it:

  * the two carriers never meet, for the legacy IPv4 fields, for an MP family, and for a
    collection which spans both at once, which is the case most likely to be wrong because
    the two are filled by separate loops;
  * a withdrawal is still sent before the announcement which replaces it;
  * a withdraw-only UPDATE carries no path attribute and an announce-only one does;
  * the split did not cost us batching, which is what keeps a table load to one message per
    thousand prefixes rather than one per prefix;
  * the overwhelmingly common shapes, withdraw-only and announce-only, still produce
    byte for byte what they produced before the split existed;
  * and an NLRI which is too wide for an MP attribute of its own is logged and left out,
    rather than raising into the reactor or being sent in a message over the negotiated size.
"""

from __future__ import annotations

import math

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection, NextHop
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri import collection as nlri_collection
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, RouteDistinguisher
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

CODE = Attribute.CODE

BGP_HEADER_SIZE = 19
# The withdrawn routes length and the total path attribute length, two octets each.
UPDATE_LENGTH_FIELDS_SIZE = 4

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)
IPV6_UNICAST = (AFI.ipv6, SAFI.unicast)
VPNV4 = (AFI.ipv4, SAFI.mpls_vpn)

# What a lone IPv4 withdrawal and a lone IPv4 announcement of one /24 have looked like
# since long before the carriers were split, recorded here because a regression in the
# common shape would be worse than the bug the split fixed.  The withdrawal carries a four
# byte Withdrawn Routes field and a zero length attribute field; the announcement carries
# ORIGIN, AS_PATH and NEXT_HOP and a four byte NLRI field.
IPV4_WITHDRAW_ONLY = bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001B020004180A00010000')
IPV4_ANNOUNCE_ONLY = bytes.fromhex(
    'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF002F02000000144001010040020602010000FDE9400304C0000201180A0000'
)


def session() -> Negotiated:
    """An EBGP session which has negotiated the three families these tests use."""
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = True
    negotiated.families = [IPV4_UNICAST, IPV6_UNICAST, VPNV4]
    return negotiated


def routed(prefix: str) -> RoutedNLRI:
    """One unicast route with a next hop of its own family, ready to be packed."""
    address, mask = prefix.split('/')
    ip = IP.from_string(address)
    nlri = INET.from_cidr(CIDR.create_cidr(ip.pack_ip(), int(mask)), ip.afi, SAFI.unicast)
    return RoutedNLRI(nlri, IP.from_string('192.0.2.1' if ip.afi == AFI.ipv4 else '2001:db8::ffff'))


def vpn_routed(prefix: str, label: int = 800) -> RoutedNLRI:
    """One VPNv4 route, so the MP path is exercised by a second, labelled family."""
    address, mask = prefix.split('/')
    ip = IP.from_string(address)
    nlri = IPVPN.make_vpn_route(
        AFI.ipv4,
        SAFI.mpls_vpn,
        ip.pack_ip(),
        int(mask),
        Labels.make_labels([label]),
        RouteDistinguisher.make_from_elements('1.2.3.4', 5),
    )
    return RoutedNLRI(nlri, IP.from_string('192.0.2.1'))


def next_hop_attributes() -> AttributeCollection:
    """The attributes a legacy IPv4 announcement needs, since NEXT_HOP is not implied."""
    attributes = AttributeCollection()
    attributes.add(NextHop.from_string('192.0.2.1'))
    return attributes


def attribute_codes(message: bytes) -> list[int]:
    """The path attribute type codes of one generated UPDATE, in the order they are sent."""
    body = message[BGP_HEADER_SIZE:]
    withdrawn_length = int.from_bytes(body[0:2], 'big')
    start = UPDATE_LENGTH_FIELDS_SIZE + withdrawn_length
    length = int.from_bytes(body[2 + withdrawn_length : start], 'big')
    attributes = body[start : start + length]

    codes: list[int] = []
    offset = 0
    while offset < len(attributes):
        flag, code = attributes[offset], attributes[offset + 1]
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            value_length = int.from_bytes(attributes[offset + 2 : offset + 4], 'big')
            offset += 4
        else:
            value_length = attributes[offset + 2]
            offset += 3
        codes.append(code)
        offset += value_length
    return codes


def carriers(message: bytes) -> list[str]:
    """Which of the four NLRI carriers RFC 7606 5.1 counts are present in this UPDATE."""
    body = message[BGP_HEADER_SIZE:]
    withdrawn_length = int.from_bytes(body[0:2], 'big')
    start = UPDATE_LENGTH_FIELDS_SIZE + withdrawn_length
    attributes_length = int.from_bytes(body[2 + withdrawn_length : start], 'big')
    codes = attribute_codes(message)

    present = []
    if withdrawn_length:
        present.append('withdrawn routes')
    if len(body) > start + attributes_length:
        present.append('NLRI')
    if CODE.MP_REACH_NLRI in codes:
        present.append('MP_REACH_NLRI')
    if CODE.MP_UNREACH_NLRI in codes:
        present.append('MP_UNREACH_NLRI')
    return present


def generated(
    announces: list[RoutedNLRI],
    withdraws: list[NLRI],
    attributes: AttributeCollection | None = None,
    negotiated: Negotiated | None = None,
) -> list[bytes]:
    """Every UPDATE the collection produces, checked to fit the negotiated message size."""
    negotiated = negotiated if negotiated is not None else session()
    collection = UpdateCollection(announces, withdraws, attributes if attributes is not None else AttributeCollection())
    messages = list(collection.messages(negotiated))
    for message in messages:
        assert len(message) <= negotiated.msg_size, 'a generated UPDATE was larger than the negotiated message size'
    return messages


def decoded(messages: list[bytes], negotiated: Negotiated) -> tuple[list[str], list[str]]:
    """The prefixes the whole sequence announces and withdraws, read back off the wire."""
    announced: list[str] = []
    withdrawn: list[str] = []
    for message in messages:
        parsed = Update.unpack_message(message[BGP_HEADER_SIZE:], negotiated)
        assert isinstance(parsed, Update), 'a generated message was not an UPDATE'
        collection = parsed.parse(negotiated)
        announced.extend(str(entry.nlri) for entry in collection.announces)
        withdrawn.extend(str(nlri) for nlri in collection.withdraws)
    return announced, withdrawn


def one_carrier_each(messages: list[bytes]) -> None:
    """RFC 7606 5.1 in one assertion, applied to every message of a sequence."""
    assert messages, 'no UPDATE was generated at all'
    for index, message in enumerate(messages):
        present = carriers(message)
        assert len(present) == 1, f'UPDATE {index} carried {" and ".join(present) or "no NLRI at all"}'


# ------------------------------------------------------- the carriers never share a message


def test_an_ipv4_announce_and_withdraw_come_out_as_two_messages() -> None:
    """The legacy fields: Withdrawn Routes and NLRI used to be filled in the same UPDATE."""
    messages = generated([routed('10.0.0.0/24')], [routed('10.0.1.0/24').nlri], next_hop_attributes())

    assert len(messages) == 2, f'one announce and one withdraw made {len(messages)} messages'
    one_carrier_each(messages)
    assert [carriers(message)[0] for message in messages] == ['withdrawn routes', 'NLRI']


def test_the_split_messages_are_what_the_two_collections_would_have_sent_on_their_own() -> None:
    """Byte for byte: the split is a separation, not a re-encoding of either half."""
    messages = generated([routed('10.0.0.0/24')], [routed('10.0.1.0/24').nlri], next_hop_attributes())

    assert messages == [IPV4_WITHDRAW_ONLY, IPV4_ANNOUNCE_ONLY]


def test_an_mp_reach_and_an_mp_unreach_come_out_as_two_messages() -> None:
    """The same rule for the attribute carriers, here IPv6 unicast."""
    messages = generated([routed('2001:db8::1/128')], [routed('2001:db8::2/128').nlri])

    assert len(messages) == 2, f'one IPv6 announce and one IPv6 withdraw made {len(messages)} messages'
    one_carrier_each(messages)
    assert [carriers(message)[0] for message in messages] == ['MP_UNREACH_NLRI', 'MP_REACH_NLRI']


def test_a_labelled_vpn_family_splits_its_carriers_too() -> None:
    """VPNv4 rather than IPv6, because the MP loop is meant to be family agnostic."""
    messages = generated([vpn_routed('10.0.0.0/24')], [vpn_routed('10.0.1.0/24').nlri])

    assert len(messages) == 2, f'one VPNv4 announce and one VPNv4 withdraw made {len(messages)} messages'
    one_carrier_each(messages)
    assert [carriers(message)[0] for message in messages] == ['MP_UNREACH_NLRI', 'MP_REACH_NLRI']


def test_the_mp_nlri_attribute_is_sent_before_any_other() -> None:
    """RFC 7606 5.1 again: the MP attribute "SHALL be encoded as the very first"."""
    messages = generated([routed('2001:db8::1/128')], [routed('2001:db8::2/128').nlri])

    for message in messages:
        codes = attribute_codes(message)
        assert codes, 'an UPDATE was generated with no attributes at all'
        assert codes[0] in (CODE.MP_REACH_NLRI, CODE.MP_UNREACH_NLRI), (
            f'the first attribute sent was {Attribute.CODE.name(codes[0])}'
        )


def test_a_collection_spanning_the_legacy_fields_and_an_mp_family_splits_all_four() -> None:
    """The shape most likely to be wrong: the two carriers are filled by separate loops."""
    negotiated = session()
    announces = [routed('10.0.0.0/24'), routed('2001:db8::1/128')]
    withdraws = [routed('10.0.1.0/24').nlri, routed('2001:db8::2/128').nlri]
    messages = generated(announces, withdraws, next_hop_attributes(), negotiated)

    assert len(messages) == 4, f'two families announcing and withdrawing made {len(messages)} messages'
    one_carrier_each(messages)
    assert sorted(carriers(message)[0] for message in messages) == [
        'MP_REACH_NLRI',
        'MP_UNREACH_NLRI',
        'NLRI',
        'withdrawn routes',
    ]

    announced, withdrawn = decoded(messages, negotiated)
    assert sorted(announced) == ['10.0.0.0/24', '2001:db8::1/128'], 'the split lost an announcement'
    assert sorted(withdrawn) == ['10.0.1.0/24', '2001:db8::2/128'], 'the split lost a withdrawal'


# ---------------------------------------------------------------------------------- ordering


def test_a_prefix_withdrawn_and_reannounced_is_withdrawn_first() -> None:
    """The other order leaves the peer holding, briefly, a route it was told to drop."""
    negotiated = session()
    announce = routed('10.0.0.0/24')
    messages = generated([announce], [announce.nlri], next_hop_attributes(), negotiated)

    assert len(messages) == 2
    assert carriers(messages[0]) == ['withdrawn routes'], 'the announcement was sent before its own withdrawal'
    assert carriers(messages[1]) == ['NLRI']


def test_an_mp_prefix_withdrawn_and_reannounced_is_withdrawn_first() -> None:
    """The MP loop has to keep the ordering the shared message used to give for free."""
    negotiated = session()
    announce = routed('2001:db8::1/128')
    messages = generated([announce], [announce.nlri], None, negotiated)

    assert len(messages) == 2
    assert carriers(messages[0]) == ['MP_UNREACH_NLRI'], 'the MP_REACH was sent before its own MP_UNREACH'
    assert carriers(messages[1]) == ['MP_REACH_NLRI']


def test_every_withdrawal_precedes_every_announcement_across_many_messages() -> None:
    """With several messages each way the rule still has to hold at the sequence level."""
    negotiated = session()
    announces = [routed(f'10.{index // 256}.{index % 256}.0/24') for index in range(2500)]
    withdraws = [routed(f'11.{index // 256}.{index % 256}.0/24').nlri for index in range(2500)]
    messages = generated(announces, withdraws, next_hop_attributes(), negotiated)

    one_carrier_each(messages)
    names = [carriers(message)[0] for message in messages]
    assert names.count('withdrawn routes') > 1, 'this shape is meant to need several withdrawal messages'
    assert names.count('NLRI') > 1, 'this shape is meant to need several announcement messages'
    assert names == sorted(names, key=lambda name: name != 'withdrawn routes'), (
        'an announcement was sent before a withdrawal'
    )


# -------------------------------------------------------------------- path attribute content


def test_suppressing_the_withdrawals_leaves_the_announcements_alone() -> None:
    """A session which must not replay withdrawals still has to send everything else."""
    negotiated = session()
    announces = [routed('10.0.0.0/24'), routed('2001:db8::1/128')]
    withdraws = [routed('10.0.1.0/24').nlri, routed('2001:db8::2/128').nlri]
    collection = UpdateCollection(announces, withdraws, next_hop_attributes())
    messages = list(collection.messages(negotiated, include_withdraw=False))

    assert sorted(carriers(message)[0] for message in messages) == ['MP_REACH_NLRI', 'NLRI']
    announced, withdrawn = decoded(messages, negotiated)
    assert sorted(announced) == ['10.0.0.0/24', '2001:db8::1/128']
    assert withdrawn == [], 'a withdrawal was sent although they were suppressed'


def test_a_withdraw_only_update_carries_no_path_attribute() -> None:
    """RFC 4271 4.3 makes the field optional, and it describes routes being announced."""
    messages = generated([], [routed('10.0.1.0/24').nlri], next_hop_attributes())

    assert len(messages) == 1
    assert attribute_codes(messages[0]) == [], 'a withdraw-only UPDATE carried path attributes'


def test_an_announce_only_update_carries_its_path_attributes() -> None:
    messages = generated([routed('10.0.0.0/24')], [], next_hop_attributes())

    assert len(messages) == 1
    assert attribute_codes(messages[0]) == [CODE.ORIGIN, CODE.AS_PATH, CODE.NEXT_HOP]


def test_the_withdrawal_message_of_a_mixed_collection_carries_no_path_attribute() -> None:
    """The attributes belong to the announce, and must not be copied onto the withdrawal."""
    messages = generated([routed('10.0.0.0/24')], [routed('10.0.1.0/24').nlri], next_hop_attributes())

    assert attribute_codes(messages[0]) == [], 'the split copied the announce attributes onto the withdrawal'
    assert attribute_codes(messages[1]) == [CODE.ORIGIN, CODE.AS_PATH, CODE.NEXT_HOP]


# ------------------------------------------------------------------- the common shapes, byte for byte


def test_a_withdraw_only_collection_still_produces_exactly_what_it_did() -> None:
    assert generated([], [routed('10.0.1.0/24').nlri], next_hop_attributes()) == [IPV4_WITHDRAW_ONLY]


def test_an_announce_only_collection_still_produces_exactly_what_it_did() -> None:
    assert generated([routed('10.0.0.0/24')], [], next_hop_attributes()) == [IPV4_ANNOUNCE_ONLY]


# ------------------------------------------------------------------------------------ batching


def minimum_messages(count: int, packed_size: int, budget: int) -> int:
    """How many messages a perfectly packed run of identical NLRI needs."""
    return math.ceil(count / (budget // packed_size))


def full_enough(messages: list[bytes], negotiated: Negotiated, packed_size: int) -> None:
    """Every message but the last of a run must have no room left for one more NLRI."""
    for message in messages[:-1]:
        assert len(message) + packed_size > negotiated.msg_size, (
            f'a message of {len(message)} bytes had room for another {packed_size} byte NLRI'
        )


def test_batching_survives_the_split_on_the_legacy_ipv4_fields() -> None:
    """One message per thousand prefixes, not one per prefix: a table load depends on it."""
    negotiated = session()
    count = 2500
    announces = [routed(f'10.{index // 256}.{index % 256}.0/24') for index in range(count)]
    withdraws = [routed(f'11.{index // 256}.{index % 256}.0/24').nlri for index in range(count)]
    messages = generated(announces, withdraws, next_hop_attributes(), negotiated)

    # One length octet and three prefix octets for a /24.
    packed_size = 4
    withdrawal_messages = [message for message in messages if carriers(message) == ['withdrawn routes']]
    announcement_messages = [message for message in messages if carriers(message) == ['NLRI']]
    assert len(withdrawal_messages) + len(announcement_messages) == len(messages)

    # The withdrawals have the whole message to themselves; the announcements pay for the
    # path attributes, so their budget is smaller and their run can be one message longer.
    withdrawal_budget = negotiated.msg_size - BGP_HEADER_SIZE - UPDATE_LENGTH_FIELDS_SIZE
    assert len(withdrawal_messages) == minimum_messages(count, packed_size, withdrawal_budget)
    assert len(announcement_messages) <= minimum_messages(count, packed_size, withdrawal_budget) + 1

    full_enough(withdrawal_messages, negotiated, packed_size)
    full_enough(announcement_messages, negotiated, packed_size)

    announced, withdrawn = decoded(messages, negotiated)
    assert len(announced) == count and len(withdrawn) == count, 'batching dropped a prefix'


def test_batching_survives_the_split_on_an_mp_family() -> None:
    """The MP loop batches through MPNLRICollection, which the split also had to leave alone."""
    negotiated = session()
    count = 800
    announces = [routed(f'2001:db8:0:{index:x}::1/128') for index in range(count)]
    withdraws = [routed(f'2001:db8:1:{index:x}::1/128').nlri for index in range(count)]
    messages = generated(announces, withdraws, None, negotiated)

    # One mask octet and sixteen address octets for a /128.
    packed_size = 17
    unreach = [message for message in messages if carriers(message) == ['MP_UNREACH_NLRI']]
    reach = [message for message in messages if carriers(message) == ['MP_REACH_NLRI']]
    assert len(unreach) + len(reach) == len(messages), 'an MP message carried something else as well'
    assert len(unreach) > 1 and len(reach) > 1, 'this shape is meant to need several messages each way'
    assert len(messages) < count, 'the MP path degraded towards one message per prefix'

    full_enough(unreach, negotiated, packed_size)
    full_enough(reach, negotiated, packed_size)

    announced, withdrawn = decoded(messages, negotiated)
    assert len(announced) == count and len(withdrawn) == count, 'MP batching dropped a prefix'


def test_a_partial_mp_unreach_chunk_is_not_glued_to_the_first_mp_reach() -> None:
    """The leftover of a withdrawal run is small, and used to be sent with the first reach."""
    negotiated = session()
    withdraws = [routed(f'2001:db8:1:{index:x}::1/128').nlri for index in range(300)]
    announces = [routed(f'2001:db8:0:{index:x}::1/128') for index in range(5)]
    messages = generated(announces, withdraws, None, negotiated)

    names = [carriers(message) for message in messages]
    assert all(len(present) == 1 for present in names), f'an UPDATE carried two carriers: {names}'
    assert names[-1] == ['MP_REACH_NLRI'], 'the announcement is the last thing sent'
    assert names.count(['MP_UNREACH_NLRI']) > 1, 'this shape is meant to need several withdrawal messages'


# ------------------------------------------- the announce budget must not decide a withdrawal


# A GenericAttribute in the Extended Length encoding: flag, type code, two length octets.
GENERIC_ATTRIBUTE_HEADER_SIZE = 4
PADDING_ATTRIBUTE_CODE = 200


def attributes_leaving(negotiated: Negotiated, remaining_bytes: int) -> AttributeCollection:
    """Attributes padded so an announcement has exactly `remaining_bytes` left for its NLRI.

    Derived from what the session actually packs rather than from a constant, so the shape
    survives a change to the default attributes an announcement carries.
    """
    attributes = next_hop_attributes()
    target = negotiated.msg_size - BGP_HEADER_SIZE - UPDATE_LENGTH_FIELDS_SIZE - remaining_bytes
    padding = target - len(attributes.pack_attribute(negotiated, True)) - GENERIC_ATTRIBUTE_HEADER_SIZE
    assert padding >= 0, 'the negotiated message size is too small to build this shape'
    flag = Attribute.Flag.OPTIONAL | Attribute.Flag.EXTENDED_LENGTH
    attributes.add(GenericAttribute(bytes(padding), PADDING_ATTRIBUTE_CODE, flag))
    packed_size = len(attributes.pack_attribute(negotiated, True))
    assert packed_size == target, f'the padding is off by {target - packed_size} bytes'
    return attributes


def test_a_withdrawal_is_not_dropped_because_the_announce_attributes_are_too_large() -> None:
    """A withdrawal which is not sent is a stale route on the peer, and says so nowhere.

    RFC 4271 4.3 makes the Path Attributes field optional and RFC 4760 3 says an UPDATE
    carrying MP_UNREACH_NLRI needs no other path attributes, so what an announcement cannot
    afford has no bearing on a withdrawal.  Two guards used to return from the whole method
    on the announce budget and took the pending withdrawals with them.
    """
    negotiated = session()
    messages = generated([], [routed('10.0.1.0/24').nlri], attributes_leaving(negotiated, 0), negotiated)

    assert [carriers(message) for message in messages] == [['withdrawn routes']], 'the withdrawal was dropped'
    assert attribute_codes(messages[0]) == [], 'the withdrawal carried the attributes it was blamed for'


def test_a_mixed_collection_sends_its_withdrawal_when_the_announcement_cannot_be_packed() -> None:
    """Only the announcement is impossible, and only the announcement is refused."""
    negotiated = session()
    attributes = attributes_leaving(negotiated, 0)
    messages = generated([routed('10.0.0.0/24')], [routed('10.0.1.0/24').nlri], attributes, negotiated)

    assert [carriers(message) for message in messages] == [['withdrawn routes']]
    announced, withdrawn = decoded(messages, negotiated)
    assert withdrawn == ['10.0.1.0/24'], 'the withdrawal was dropped with the announcement'
    assert announced == [], 'an announcement went out which does not fit in an UPDATE'


def test_an_announcement_which_cannot_be_packed_is_still_refused() -> None:
    """The refusal is the point of the guard and has to survive it being moved."""
    negotiated = session()
    messages = generated([routed('10.0.0.0/24')], [], attributes_leaving(negotiated, 0), negotiated)

    assert messages == [], 'an UPDATE was generated for an announcement which cannot be packed'


def test_an_announcement_wider_than_what_is_left_is_refused_after_the_withdrawal_is_sent() -> None:
    """The other refusal: the budget is positive, and one NLRI still does not fit in it."""
    negotiated = session()
    # Three octets left, and the shortest NLRI here is a /24, which needs four.
    attributes = attributes_leaving(negotiated, 3)
    messages = generated([routed('10.0.0.0/24')], [routed('10.0.1.0/24').nlri], attributes, negotiated)

    assert [carriers(message) for message in messages] == [['withdrawn routes']]
    announced, withdrawn = decoded(messages, negotiated)
    assert withdrawn == ['10.0.1.0/24']
    assert announced == []


def test_an_unpackable_mp_withdrawal_is_refused_rather_than_raised() -> None:
    """A budget which cannot hold an attribute header at all is refused by the caller.

    A withdraw-only VPNv4 collection keeps its path attributes, unlike a unicast one, so it
    is the shape where an MP withdrawal can be unaffordable.  Removing the guards which used
    to return long before this point is only safe because the MP loop now checks its own
    budget.  The guard here stays so that one fact about the attributes is logged once rather
    than once per route, which is what the generator below it would do.
    """
    negotiated = session()
    messages = generated([], [vpn_routed('10.0.1.0/24').nlri], attributes_leaving(negotiated, 0), negotiated)

    assert messages == [], 'an UPDATE was generated for a withdrawal which cannot be packed'


# --------------------------------------- an NLRI we can not encode is dropped, not raised


def test_a_lone_mp_announcement_wider_than_the_budget_is_dropped_rather_than_raised() -> None:
    """One NLRI too wide for an MP_REACH_NLRI of its own used to raise RuntimeError.

    Nothing between here and `Peer._run`'s last resort `except Exception` catches it, so a
    route of our own which will not fit reset an established session.  The peer had done
    nothing and lost every route of every family, and the route is still in the RIB on the
    next session, which makes it a flap loop rather than a failure.  A local encoding limit
    is not a protocol error: it is logged and the NLRI is left out, which is what the native
    IPv4 pass has always done.
    """
    negotiated = session()
    # An MP_REACH_NLRI for IPv6 unicast spends 21 octets on AFI, SAFI, a 16 byte next-hop and
    # the reserved octet, before its first NLRI, so ten leaves room for none of it.
    messages = generated([routed('2001:db8::/64')], [], attributes_leaving(negotiated, 10), negotiated)

    assert messages == [], 'an UPDATE was generated for an announcement which cannot be packed'


def test_a_lone_mp_withdrawal_wider_than_the_budget_is_dropped_rather_than_raised() -> None:
    """The MP_UNREACH half of the same defect: the same two lines, the same escape."""
    negotiated = session()
    messages = generated([], [vpn_routed('10.0.1.0/24').nlri], attributes_leaving(negotiated, 10), negotiated)

    assert messages == [], 'an UPDATE was generated for a withdrawal which cannot be packed'


def test_an_mp_announcement_wider_than_the_budget_does_not_oversize_the_message() -> None:
    """The same NLRI behind one which fits produced an UPDATE over the negotiated size.

    An NLRI which overflows the current attribute opens the next one, and nothing asked
    whether it fits there either, so the last fragment came out wider than the budget.  RFC
    4271 4.1 gives the maximum message size, and 6.1 makes the peer answer a message over it
    with a NOTIFICATION, so this took the session down from the other end instead.

    The NLRIs of a family are sorted by their packed form, which begins with the mask, so the
    widest is normally the last of its group: this is the shape the defect takes in practice.
    """
    negotiated = session()
    # Thirty octets past the MP_REACH header holds the /8 which needs two and not the /64
    # which needs nine.
    messages = generated(
        [routed('2001:db8::/64'), routed('2000::/8')], [], attributes_leaving(negotiated, 30), negotiated
    )

    announced, withdrawn = decoded(messages, negotiated)
    assert announced == ['2000::/8'], 'the NLRI which fits was dropped with the one which did not'
    assert withdrawn == []


def test_an_mp_withdrawal_wider_than_the_budget_does_not_oversize_the_message() -> None:
    """The MP_UNREACH half: a withdraw-only VPNv4 collection still carries its attributes."""
    negotiated = session()
    # MP_UNREACH_NLRI spends three octets on AFI and SAFI, and a VPNv4 NLRI carries a label
    # and a route distinguisher, so twenty holds the /8 at thirteen octets and not the /32 at
    # sixteen.
    withdraws = [vpn_routed('10.0.0.1/32').nlri, vpn_routed('10.0.0.0/8').nlri]
    messages = generated([], withdraws, attributes_leaving(negotiated, 20), negotiated)

    announced, withdrawn = decoded(messages, negotiated)
    expected = '10.0.0.0/8 label 800 (12801) rd 1.2.3.4:5'
    assert withdrawn == [expected], 'the NLRI which fits was dropped with the one which did not'
    assert announced == []


def test_a_family_which_can_hold_no_nlri_at_all_is_reported_once(monkeypatch) -> None:
    """One critical line for the family, not one per route, which is a log flood.

    The budget is what is left of an UPDATE once our attributes are in it, so a budget too
    narrow for the attribute header plus a single octet says one thing about the attributes and
    nothing about any particular route.  Reporting it per NLRI would write a critical line per
    route on every pass over a RIB which still holds them.
    """
    negotiated = session()
    reported: list[str] = []
    # The patch goes through the module under test rather than through `exabgp.logger`, because
    # tests/unit/test_rib_flush_async.py replaces sys.modules['exabgp.logger'] with a MagicMock
    # at import time and never puts it back.  Every test module collected after it, which is
    # every one later in the alphabet, binds a mock with `from exabgp.logger import log`, and
    # patching that mock patches nothing the encoder can see: this asserted on zero calls and
    # would have passed whatever the encoder logged.
    monkeypatch.setattr(nlri_collection.log, 'critical', lambda message, source='': reported.append(message()))

    announces = [routed('2001:db8::/64'), routed('2001:db9::/64'), routed('2001:dba::/64')]
    messages = generated(announces, [], attributes_leaving(negotiated, 10), negotiated)

    assert messages == [], 'an UPDATE was generated for a family which cannot hold one NLRI'
    assert len(reported) == 1, f'three routes were refused in {len(reported)} log lines'
    assert 'afi=ipv6 safi=unicast' in reported[0], 'the log does not say which family was refused'
    assert 'nlri_count=3' in reported[0], 'the log does not say how many routes were dropped'
