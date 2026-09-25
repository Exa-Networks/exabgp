"""RFC 9234: BGP Roles, the Role capability, and the Only to Customer attribute.

Route leak prevention is the one feature here where a wrong MUST puts somebody else's
prefix where it should never have gone, so every requirement is driven through wire bytes
rather than through a helper: the OPEN capabilities are packed and unpacked, and the
UPDATEs are built by hand as octets and handed to the real decoder.

The ledger entries these prove are in qa/rfc/rfc9234.toml.
"""

from __future__ import annotations

from struct import pack
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.capability.role import Role, RoleValue
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.otc import OTC
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.api import API
from exabgp.rib import RIB


LOCAL_AS = 65537
PEER_AS = 65002
OTHER_AS = 64500

# RFC 9234 section 5: the OTC attribute is type code 35, optional and transitive.
OTC_CODE = 35
OPTIONAL_TRANSITIVE = 0xC0

# A minimal well formed set of mandatory attributes, so the decoder has no reason to
# reject the UPDATE for anything other than what a test is about.
ORIGIN_IGP = bytes([0x40, 0x01, 0x01, 0x00])
EMPTY_AS_PATH = bytes([0x40, 0x02, 0x00])
NEXT_HOP = bytes([0x40, 0x03, 0x04, 192, 0, 2, 1])
PREFIX_10_0_0_0_24 = bytes([24, 10, 0, 0])


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """RIB keeps a process wide cache keyed by neighbour name; tests must not share it."""
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour(role: str | None = 'provider', extra: str = '') -> Neighbor:
    """A neighbour built by the real configuration parser, eBGP as RFC 9234 requires."""
    block = f'role {{ local {role}; {extra} }}' if role else ''
    text = f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as {LOCAL_AS};
    peer-as {PEER_AS};
    {block}
    family {{ ipv4 unicast; ipv6 unicast; ipv4 multicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    parsed: Neighbor = next(iter(configuration.neighbors.values()))
    return parsed


def our_capabilities(neighbor: Neighbor) -> Capabilities:
    return Capabilities().new(neighbor, False, local_as=ASN(LOCAL_AS))


def open_message(asn: int, router_id: str, capabilities: Capabilities) -> Open:
    return Open.make_open(Version(4), ASN(asn), HoldTime(180), RouterID(router_id), capabilities)


def negotiate(neighbor: Neighbor, peer_role: RoleValue | None) -> Negotiated:
    """Run the real OPEN negotiation with a peer holding the role we nominate.

    `peer_role` of None is a peer which sent no Role capability at all, which is the
    backward compatibility case of section 4.2.
    """
    sent = our_capabilities(neighbor)
    received = Capabilities(sent)
    received.pop(Capability.CODE.ROLE, None)
    if peer_role is not None:
        received[Capability.CODE.ROLE] = Role(peer_role)

    negotiated = Negotiated.make_negotiated(neighbor, Direction.OUT)
    negotiated.sent(open_message(LOCAL_AS, '192.0.2.2', sent))
    negotiated.received(open_message(PEER_AS, '192.0.2.1', received))
    return negotiated


def capability_codes(packed: bytes) -> list[int]:
    """Every capability code in a packed OPEN parameter block, repeats included.

    Counting rather than looking up is the point: a dict would hide a second instance of
    a capability, and section 4.1 is about what leaves on the wire.
    """
    codes: list[int] = []
    total = packed[0] if packed else 0
    offset = 1
    while offset < 1 + total:
        kind, length = packed[offset], packed[offset + 1]
        assert kind == 2, 'only the capability optional parameter is expected here'
        end = offset + 2 + length
        inner = offset + 2
        while inner < end:
            codes.append(packed[inner])
            inner += 2 + packed[inner + 1]
        offset = end
    return codes


def role_capability_bytes(*roles: RoleValue) -> bytes:
    """A capability optional parameter block carrying the Role capability N times."""
    tlvs = b''.join(bytes([Capability.CODE.ROLE, 1, int(role)]) for role in roles)
    parameter = bytes([2, len(tlvs)]) + tlvs
    return bytes([len(parameter)]) + parameter


def update_payload(attributes: bytes, nlri: bytes = PREFIX_10_0_0_0_24) -> bytes:
    """A complete UPDATE payload, as it arrives after the nineteen byte header."""
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes + nlri


def otc_attribute(asn: int) -> bytes:
    return bytes([OPTIONAL_TRANSITIVE, OTC_CODE, 4]) + pack('!L', asn)


def received_update(negotiated: Negotiated, attributes: bytes, nlri: bytes = PREFIX_10_0_0_0_24) -> UpdateCollection:
    """Decode wire bytes the way reactor/protocol.py does, then run the ingress check."""
    message = Update.unpack_message(update_payload(attributes, nlri), negotiated)
    assert isinstance(message, Update)
    collection = message.parse(negotiated)
    collection.classify_otc(negotiated)
    return collection


def announced_attributes(neighbor: Neighbor, negotiated: Negotiated, command: str) -> list[AttributeCollection]:
    """The attributes of every UPDATE this neighbour really puts on the wire for a route.

    The route goes through the outgoing RIB rather than straight into an UpdateCollection,
    because the egress suppression of Section 5 lives in OutgoingRIB._otc_allowed: a route
    which must not be propagated never reaches the encoder at all, and a test which built
    the UpdateCollection by hand would step over the check it is supposed to exercise.
    """
    api = API(Mock())
    parse = {'route': api.api_route, 'ipv4': api.api_announce_v4, 'ipv6': api.api_announce_v6}[command.split()[0]]
    routes = parse(command, 'announce')
    assert len(routes) == 1, f'{command!r} did not parse to one route'
    neighbor.rib.outgoing.add_to_rib(routes[0])

    decoded: list[AttributeCollection] = []
    for update in neighbor.rib.outgoing.updates(True, None, negotiated):
        if not isinstance(update, UpdateCollection) or not update.announces:
            continue
        for wire in update.messages(negotiated):
            message = Update.unpack_message(wire[19:], negotiated)
            if isinstance(message, Update):
                decoded.append(message.parse(negotiated).attributes)
    return decoded


# ============================================================ 4.1 the capability


@pytest.mark.rfc('rfc9234#4.1-advertise-role-capability')
@pytest.mark.parametrize('name, value', [('provider', 0), ('rs', 1), ('rs-client', 2), ('customer', 3), ('peer', 4)])
def test_a_configured_role_is_advertised_in_the_open(name: str, value: int) -> None:
    """Every configured role reaches the wire, provider included.

    Provider is role 0, so an implementation testing truthiness anywhere in this path
    silently stops advertising exactly the role which hands routes to customers.
    """
    packed = our_capabilities(neighbour(name)).pack_capabilities()

    assert Capability.CODE.ROLE in capability_codes(packed), f'{name} was configured and no Role capability was sent'
    assert Capabilities.unpack(packed).role() == value


@pytest.mark.rfc('rfc9234#4.1-advertise-role-capability', polarity='negative')
def test_no_configured_role_advertises_no_capability() -> None:
    """Without a role block there is nothing to claim, and claiming one is a false pair."""
    packed = our_capabilities(neighbour(None)).pack_capabilities()

    assert Capability.CODE.ROLE not in capability_codes(packed), 'a Role capability was invented'
    assert Capabilities.unpack(packed).role() == RoleValue.NO_ROLE


@pytest.mark.rfc('rfc9234#4.1-single-role-capability')
def test_the_role_capability_is_sent_exactly_once() -> None:
    packed = our_capabilities(neighbour('customer')).pack_capabilities()

    codes = capability_codes(packed)
    assert codes.count(Capability.CODE.ROLE) == 1, f'the Role capability appears {codes.count(9)} times'


# ============================================================ 4.2 role correctness


ALLOWED = [
    (RoleValue.PROVIDER, RoleValue.CUSTOMER),
    (RoleValue.CUSTOMER, RoleValue.PROVIDER),
    (RoleValue.RS, RoleValue.RS_CLIENT),
    (RoleValue.RS_CLIENT, RoleValue.RS),
    (RoleValue.PEER, RoleValue.PEER),
]

REFUSED = [
    (RoleValue.PROVIDER, RoleValue.PROVIDER),
    (RoleValue.PROVIDER, RoleValue.PEER),
    (RoleValue.PROVIDER, RoleValue.RS),
    (RoleValue.CUSTOMER, RoleValue.CUSTOMER),
    (RoleValue.CUSTOMER, RoleValue.PEER),
    (RoleValue.PEER, RoleValue.PROVIDER),
    (RoleValue.PEER, RoleValue.CUSTOMER),
    (RoleValue.RS, RoleValue.RS),
    (RoleValue.RS, RoleValue.CUSTOMER),
    (RoleValue.RS_CLIENT, RoleValue.RS_CLIENT),
    (RoleValue.RS_CLIENT, RoleValue.CUSTOMER),
]


@pytest.mark.rfc('rfc9234#4.2-roles-must-correspond')
@pytest.mark.parametrize('local, remote', ALLOWED, ids=[f'{a}-{b}' for a, b in ALLOWED])
def test_the_pairs_of_table_2_establish(local: RoleValue, remote: RoleValue) -> None:
    neighbor = neighbour(str(local))
    negotiated = negotiate(neighbor, remote)

    assert negotiated.validate(neighbor) is None, f'{local} with {remote} is in Table 2 and was refused'
    assert negotiated.peer_role == remote


@pytest.mark.rfc('rfc9234#4.2-roles-must-correspond', polarity='negative')
@pytest.mark.parametrize('local, remote', REFUSED, ids=[f'{a}-{b}' for a, b in REFUSED])
def test_a_pair_outside_table_2_is_a_role_mismatch(local: RoleValue, remote: RoleValue) -> None:
    """The session must not come up, and the subcode has to be 11 rather than a generic 0.

    The subcode is what tells the operator at the far end that the two configurations
    disagree about the relationship rather than that the bytes were bad.
    """
    neighbor = neighbour(str(local))
    negotiated = negotiate(neighbor, remote)

    error = negotiated.validate(neighbor)

    assert error is not None, f'{local} with {remote} is not in Table 2 and the session was allowed'
    assert error[0] == 2, f'role mismatch must be an OPEN message error, got code {error[0]}'
    assert error[1] == 11, f'role mismatch must be subcode 11, got {error[1]}'


@pytest.mark.rfc('rfc9234#4.2-conflicting-role-capabilities')
def test_identical_role_capabilities_are_one_capability() -> None:
    """RFC 5492 lets a repeated capability be kept once, and two identical answers agree."""
    capabilities = Capabilities.unpack(role_capability_bytes(RoleValue.CUSTOMER, RoleValue.CUSTOMER))

    assert capabilities.role() == RoleValue.CUSTOMER


@pytest.mark.rfc('rfc9234#4.2-conflicting-role-capabilities', polarity='negative')
@pytest.mark.parametrize('first, second', [(RoleValue.CUSTOMER, RoleValue.PROVIDER), (RoleValue.PEER, RoleValue.RS)])
def test_disagreeing_role_capabilities_are_refused(first: RoleValue, second: RoleValue) -> None:
    """Keeping either one would be choosing on the peer's behalf what its role is."""
    with pytest.raises(Notify) as raised:
        Capabilities.unpack(role_capability_bytes(first, second))

    assert raised.value.code == 2
    assert raised.value.subcode == 11


@pytest.mark.rfc('rfc9234#4.2-absent-capability-ignored')
def test_a_peer_without_the_capability_still_establishes() -> None:
    """Backward compatibility: the local role alone then drives the Section 5 procedures."""
    neighbor = neighbour('provider')
    negotiated = negotiate(neighbor, None)

    assert negotiated.validate(neighbor) is None, 'a peer which does not know RFC 9234 was refused'
    assert negotiated.peer_role == RoleValue.CUSTOMER, 'the complementary role must be assumed for Section 5'


@pytest.mark.rfc('rfc9234#4.2-absent-capability-ignored', polarity='negative')
def test_strict_mode_refuses_a_peer_without_the_capability() -> None:
    """The operator asked for the confirmation, so the absence is a mismatch, not silence."""
    neighbor = neighbour('provider', 'strict enable;')
    negotiated = negotiate(neighbor, None)

    error = negotiated.validate(neighbor)

    assert error is not None, 'strict mode accepted a peer which sent no Role capability'
    assert (error[0], error[1]) == (2, 11)


# ============================================================ 5 ingress procedures


@pytest.mark.rfc('rfc9234#5-ingress-otc-from-customer-is-a-leak')
@pytest.mark.parametrize('local, peer', [('provider', 'Customer'), ('rs', 'RS-Client')])
def test_an_otc_route_from_a_customer_is_recorded_as_a_leak(local: str, peer: str) -> None:
    """The whole point of the attribute: it should never have come back up the hill."""
    neighbor = neighbour(local)
    negotiated = negotiate(neighbor, None)

    collection = received_update(negotiated, ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP + otc_attribute(OTHER_AS))

    assert collection.route_leaks, f'an OTC route from a {peer} was not detected as a leak'
    leak = collection.route_leaks[(AFI.ipv4, SAFI.unicast)]
    assert leak.received_otc == f'AS{OTHER_AS}'
    assert leak.peer_as == f'AS{PEER_AS}'


@pytest.mark.rfc('rfc9234#5-ingress-otc-from-customer-is-a-leak', polarity='negative')
def test_a_route_without_otc_from_a_customer_is_not_a_leak() -> None:
    """A false positive here marks a customer's own prefixes as leaked."""
    neighbor = neighbour('provider')
    negotiated = negotiate(neighbor, None)

    collection = received_update(negotiated, ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP)

    assert collection.route_leaks is None, 'a route with no OTC attribute was called a leak'


@pytest.mark.rfc('rfc9234#5-ingress-otc-from-customer-is-a-leak', polarity='negative')
def test_an_otc_route_from_a_provider_is_not_a_leak() -> None:
    """From above the OTC is expected, and Section 5 ingress rule 1 does not apply."""
    neighbor = neighbour('customer')
    negotiated = negotiate(neighbor, None)

    collection = received_update(negotiated, ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP + otc_attribute(PEER_AS))

    assert collection.route_leaks is None, 'a route from a Provider carrying OTC was called a leak'


@pytest.mark.rfc('rfc9234#5-ingress-otc-from-peer-must-match')
def test_an_otc_from_a_peer_naming_a_third_as_is_a_leak() -> None:
    """A Peer may only send us what it originated or learned from its own customers.

    An OTC naming somebody else is that third party's marking arriving one hop too far.
    """
    neighbor = neighbour('peer')
    negotiated = negotiate(neighbor, RoleValue.PEER)

    collection = received_update(negotiated, ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP + otc_attribute(OTHER_AS))

    assert collection.route_leaks, 'an OTC naming a third AS arrived from a Peer and was accepted silently'
    assert collection.route_leaks[(AFI.ipv4, SAFI.unicast)].received_otc == f'AS{OTHER_AS}'


@pytest.mark.rfc('rfc9234#5-ingress-otc-from-peer-must-match', polarity='negative')
def test_an_otc_from_a_peer_naming_that_peer_is_not_a_leak() -> None:
    """This is the ordinary case: our Peer marked its own route on the way out to us."""
    neighbor = neighbour('peer')
    negotiated = negotiate(neighbor, RoleValue.PEER)

    collection = received_update(negotiated, ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP + otc_attribute(PEER_AS))

    assert collection.route_leaks is None, "a Peer's own OTC value was treated as a leak"


# ============================================================ 5 egress procedures


@pytest.mark.rfc('rfc9234#5-egress-add-otc')
@pytest.mark.parametrize('local', ['provider', 'rs', 'peer'])
def test_otc_is_added_when_the_peer_is_below_us(local: str) -> None:
    """Provider to Customer, RS to RS-Client and Peer to Peer all mark on the way out."""
    neighbor = neighbour(local)
    negotiated = negotiate(neighbor, None)

    attributes = announced_attributes(neighbor, negotiated, 'route 10.0.0.0/24 next-hop 192.0.2.2')

    assert len(attributes) == 1
    otc = attributes[0].get(Attribute.CODE.OTC)
    assert isinstance(otc, OTC), f'role {local} advertised to a customer without an OTC attribute'
    assert otc.asn == LOCAL_AS, 'the OTC value must be our own AS, not the peer AS'


@pytest.mark.rfc('rfc9234#5-egress-add-otc', polarity='negative')
@pytest.mark.parametrize('local', ['customer', 'rs-client'])
def test_otc_is_not_added_when_the_peer_is_above_us(local: str) -> None:
    """Marking a route to a Provider would tell it to send the route to nobody.

    This is the half that breaks reachability rather than leaking it, and a rule applied
    in both directions would do it to every route a customer announces upstream.
    """
    neighbor = neighbour(local)
    negotiated = negotiate(neighbor, None)

    attributes = announced_attributes(neighbor, negotiated, 'route 10.0.0.0/24 next-hop 192.0.2.2')

    assert len(attributes) == 1
    assert attributes[0].get(Attribute.CODE.OTC) is None, f'role {local} marked a route sent upstream'


@pytest.mark.rfc('rfc9234#5-egress-otc-not-to-provider')
@pytest.mark.parametrize('local', ['customer', 'rs-client', 'peer'])
def test_a_route_carrying_otc_is_not_propagated_upstream(local: str) -> None:
    """The route was given to us only to hand to customers, and these peers are not."""
    neighbor = neighbour(local)
    negotiated = negotiate(neighbor, None)

    attributes = announced_attributes(neighbor, negotiated, f'route 10.0.0.0/24 next-hop 192.0.2.2 otc {OTHER_AS}')

    announced_otc = [collection.get(Attribute.CODE.OTC) for collection in attributes]
    assert not any(announced_otc), f'role {local} propagated a route carrying OTC {OTHER_AS} to a Provider, Peer or RS'


@pytest.mark.rfc('rfc9234#5-egress-otc-not-to-provider', polarity='negative')
def test_a_route_carrying_otc_still_goes_to_a_customer() -> None:
    """Suppression must be the exception, not the rule: a Provider may pass this on."""
    neighbor = neighbour('provider')
    negotiated = negotiate(neighbor, None)

    attributes = announced_attributes(neighbor, negotiated, f'route 10.0.0.0/24 next-hop 192.0.2.2 otc {OTHER_AS}')

    assert len(attributes) == 1
    otc = attributes[0].get(Attribute.CODE.OTC)
    assert isinstance(otc, OTC), 'a route with OTC was withheld from a Customer'


@pytest.mark.rfc('rfc9234#5-otc-preserved-unchanged')
def test_an_existing_otc_value_is_not_overwritten() -> None:
    """Rewriting it with our own AS would erase the evidence of where the route came from."""
    neighbor = neighbour('provider')
    negotiated = negotiate(neighbor, None)

    attributes = announced_attributes(neighbor, negotiated, f'route 10.0.0.0/24 next-hop 192.0.2.2 otc {OTHER_AS}')

    otc = attributes[0].get(Attribute.CODE.OTC)
    assert isinstance(otc, OTC)
    assert otc.asn == OTHER_AS, f'the OTC value changed from {OTHER_AS} to {otc.asn} on the way out'


@pytest.mark.rfc('rfc9234#5-otc-preserved-unchanged', polarity='negative')
def test_a_received_otc_survives_a_decode_and_re_encode() -> None:
    """What we decode we must be able to put back byte for byte, or the value drifted."""
    negotiated = negotiate(neighbour('customer'), None)
    packed = otc_attribute(OTHER_AS)

    collection = received_update(negotiated, ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP + packed)
    otc = collection.attributes[Attribute.CODE.OTC]

    assert isinstance(otc, OTC)
    assert otc.pack_attribute(negotiated) == packed, 'the re-encoded OTC attribute is not the one received'


@pytest.mark.rfc('rfc9234#5-malformed-otc-treat-as-withdraw')
@pytest.mark.parametrize('length', [0, 1, 3, 5, 8])
def test_an_otc_of_the_wrong_length_is_treated_as_a_withdraw(length: int) -> None:
    """Not a NOTIFICATION: RFC 7606 keeps the session and drops the routes.

    Tearing the session down over one bad attribute is what RFC 7606 exists to stop, and
    an attribute whose length the sender got wrong is not a reason to lose every prefix.
    """
    negotiated = negotiate(neighbour('provider'), None)
    malformed = bytes([OPTIONAL_TRANSITIVE, OTC_CODE, length]) + bytes(length)

    attributes = AttributeCollection.unpack(ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP + malformed, negotiated)

    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in attributes, (
        f'an OTC attribute of {length} bytes was accepted rather than treated as a withdraw'
    )


@pytest.mark.rfc('rfc9234#5-malformed-otc-treat-as-withdraw', polarity='negative')
def test_a_four_byte_otc_is_not_treated_as_a_withdraw() -> None:
    """The working length must not have been swept into the error path."""
    negotiated = negotiate(neighbour('provider'), None)

    attributes = AttributeCollection.unpack(ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP + otc_attribute(OTHER_AS), negotiated)

    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in attributes
    otc = attributes[Attribute.CODE.OTC]
    assert isinstance(otc, OTC) and otc.asn == OTHER_AS


# ============================================================ 5 address families


@pytest.mark.rfc('rfc9234#5-only-ipv4-ipv6-unicast')
def test_the_egress_marking_is_not_applied_to_other_families() -> None:
    """IPv4 multicast is outside the procedures, so nothing may be added to it."""
    neighbor = neighbour('provider')
    negotiated = negotiate(neighbor, None)

    attributes = announced_attributes(neighbor, negotiated, 'ipv4 multicast 10.0.0.0/24 next-hop 192.0.2.2')

    assert len(attributes) == 1
    assert attributes[0].get(Attribute.CODE.OTC) is None, 'IPv4 multicast was marked with OTC'


@pytest.mark.rfc('rfc9234#5-only-ipv4-ipv6-unicast', polarity='negative')
def test_ipv6_unicast_is_inside_the_procedures() -> None:
    """AFI 2 SAFI 1 is named by the same sentence, so leaving it out is the other error."""
    neighbor = neighbour('provider')
    negotiated = negotiate(neighbor, None)

    attributes = announced_attributes(neighbor, negotiated, 'ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1')

    assert len(attributes) == 1
    otc = attributes[0].get(Attribute.CODE.OTC)
    assert isinstance(otc, OTC), 'IPv6 unicast is in scope for RFC 9234 and was not marked'
    assert otc.asn == LOCAL_AS


@pytest.mark.rfc('rfc9234#5-operator-cannot-modify')
def test_an_operator_cannot_turn_the_egress_marking_off() -> None:
    """Section 5 closes with the one sentence an implementation cannot make optional.

    Being able to switch the marking off is how a route leak leaves this box: the
    customer downstream then has no way to tell the route was ours to give away. There is
    no longer a configuration which reaches this path with the marking suppressed, so the
    test is that the only surface an operator has still marks.
    """
    neighbor = neighbour('provider')
    negotiated = negotiate(neighbor, None)

    attributes = announced_attributes(neighbor, negotiated, 'route 10.0.0.0/24 next-hop 192.0.2.2')

    assert len(attributes) == 1
    assert isinstance(attributes[0].get(Attribute.CODE.OTC), OTC), 'the egress marking was not applied'


@pytest.mark.rfc('rfc9234#5-operator-cannot-modify')
@pytest.mark.parametrize(
    'block, wanted',
    [
        ('role { local provider; otc disable; }', "'role otc' was removed"),
        ('role { local provider; otc send; }', "'role otc' was removed"),
        (
            'role { local provider; }\n    static { route 10.0.0.0/24 { next-hop 192.0.2.2; otc none; } }',
            "'otc none' was removed",
        ),
    ],
)
def test_the_removed_suppression_options_are_refused_by_name(block: str, wanted: str) -> None:
    """A configuration which used to switch the marking off fails, and says why.

    Ignoring the line would leave an operator with a file which still parses, still reads
    as if the marking were off, and marks anyway. The two experiences are not the same, so
    the parser refuses the token and names the RFC which took the knob away.
    """
    text = f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as {LOCAL_AS};
    peer-as {PEER_AS};
    {block}
    family {{ ipv4 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)

    assert not configuration.reload(), 'a removed RFC 9234 suppression option was accepted'
    assert wanted in str(configuration.error), str(configuration.error)
    assert 'RFC 9234 section 5' in str(configuration.error), str(configuration.error)
