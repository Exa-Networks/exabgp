"""draft-ietf-idr-bgp-multisession-07, the MULTISESSION capability.

The ledger these tests are joined to is qa/rfc/draft-ietf-idr-bgp-multisession-07.toml.

The capability is decoded by MultiSession.unpack_capability and the two Session Ids are
compared in Negotiated._negotiate_multisession, which records either True or the
(code, subcode, text) the reactor sends.  What we send is built by Capabilities.new from a
parsed configuration, so those tests start from configuration text.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.capabilities import Parameter
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib import RIB

MULTISESSION = Capability.CODE.MULTISESSION
MULTIPROTOCOL = Capability.CODE.MULTIPROTOCOL

# The OPEN router D (172.16.1.2, a Cisco IOS router) sent in the PacketLife capture
# 4-byte_AS_numbers_Full_Support.cap, frame 2, captured 2010-04-30: the TCP payload less
# its 19 octet header.  It carries the Cisco multisession capability as `83 01 00`, a one
# octet value holding only the flags, each capability in its own optional parameter.
# Mirrored at https://github.com/epiecs/packetlife-backup, pcaps/, commit 4a77a47e.
CISCO_OPEN_BODY = bytes.fromhex('045ba000b4280000011d0206010400010001020280000202020002038301000206410400280001')


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def neighbours(capability: str) -> list[Neighbor]:
    text = f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65002;
    {capability}
    family {{ ipv4 unicast; ipv6 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    return list(configuration.neighbors.values())


def multiprotocol(*families: tuple[AFI, SAFI]) -> MultiProtocol:
    capability = MultiProtocol()
    capability.extend(families or [(AFI.ipv4, SAFI.unicast)])
    return capability


def ours() -> Capabilities:
    capabilities = Capabilities()
    capabilities[MULTIPROTOCOL] = multiprotocol()
    capabilities[MULTISESSION] = MultiSession().set([MULTIPROTOCOL])
    return capabilities


def received(*capabilities: tuple[int, bytes]) -> Capabilities:
    """Decode the capabilities a peer sent, from wire bytes, in one parameter."""
    tlvs = b''.join(bytes([code, len(value)]) + value for code, value in capabilities)
    parameter = bytes([Parameter.CAPABILITIES, len(tlvs)]) + tlvs
    return Capabilities.unpack(bytes([len(parameter)]) + parameter)


def ipv4_unicast() -> tuple[int, bytes]:
    return MULTIPROTOCOL, multiprotocol().extract_capability_bytes()[0]


def negotiate(sent: Capabilities, recv: Capabilities) -> bool | tuple[int, int, str]:
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    negotiated = Negotiated.make_negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(180), RouterID('192.0.2.2'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(180), RouterID('192.0.2.1'), recv))
    return negotiated.multisession


def session_id(value: bytes) -> list[int]:
    instance = MultiSession()
    MultiSession.unpack_capability(instance, value, MULTISESSION)
    return [int(code) for code in instance]


# ==============================================================================
# What we send
# ==============================================================================


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#1-implement-the-session-criteria')
@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#1-implement-mp-bgp')
@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#4-all-or-none-sessions')
@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#7-advertise-on-every-session')
@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#7-same-session-id-everywhere')
@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#10-per-peer-option')
def test_every_multisession_neighbour_announces_it_with_the_same_session_id() -> None:
    configured = neighbours('capability { multi-session enable; }')
    assert configured

    for neighbor in configured:
        capabilities = Capabilities().new(neighbor, False)
        assert capabilities.announced(MULTISESSION)
        assert capabilities.announced(MULTIPROTOCOL)
        assert list(capabilities[MULTISESSION]) == [MULTIPROTOCOL]


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#7-otherwise-not-advertised')
@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#10-disabled-by-default')
def test_a_neighbour_which_did_not_enable_it_does_not_announce_it() -> None:
    for neighbor in neighbours(''):
        capabilities = Capabilities().new(neighbor, False)
        assert not capabilities.announced(MULTISESSION)
        assert not capabilities.announced(Capability.CODE.MULTISESSION_CISCO)


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#10-support-trivial-groups')
def test_multisession_with_two_families_makes_one_session_per_family() -> None:
    configured = neighbours('capability { multi-session enable; }')

    assert [neighbor.rib.outgoing.families for neighbor in configured] == [
        {(AFI.ipv4, SAFI.unicast)},
        {(AFI.ipv6, SAFI.unicast)},
    ]
    assert len({neighbor.name() for neighbor in configured}) == 2


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#10-support-trivial-groups')
def test_each_session_advertises_its_family_alone() -> None:
    """Sessions are grouped by their MULTIPROTOCOL capability: one listing both would match neither of the peer's."""
    configured = neighbours('capability { multi-session enable; add-path send; }')

    for neighbor, family in zip(configured, [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)], strict=True):
        capabilities = Capabilities().new(neighbor, False)
        assert list(capabilities[MULTIPROTOCOL]) == [family]
        assert neighbor.families() == [family]
        assert neighbor.addpaths() == [family]
        assert neighbor.name().endswith(f'family-allowed {family[0].name()}-{family[1].name()}')


def test_a_route_is_sent_on_the_session_of_its_family() -> None:
    routes = 'static { route 10.0.0.0/24 next-hop 192.0.2.3; route 2001:db8::/32 next-hop 2001:db8::1; }'
    configured = neighbours(f'capability {{ multi-session enable; }} {routes}')

    for neighbor in configured:
        (family,) = neighbor.families()
        sent = [route.nlri.family().afi_safi() for route in neighbor.rib.outgoing.cached_routes()]
        assert sent == [family]


# ==============================================================================
# The capability value
# ==============================================================================


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#4-g-bit-is-not-relied-on')
def test_the_g_bit_does_not_change_the_session_id() -> None:
    assert session_id(bytes([0x80, MULTIPROTOCOL])) == session_id(bytes([0x00, MULTIPROTOCOL])) == [MULTIPROTOCOL]


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#4-reserved-flags')
def test_we_send_the_flags_octet_as_zero() -> None:
    (value,) = MultiSession().set([MULTIPROTOCOL]).extract_capability_bytes()

    assert value == bytes([0x00, MULTIPROTOCOL])


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#4-reserved-flags', polarity='negative')
def test_reserved_flag_bits_from_a_peer_are_ignored() -> None:
    assert session_id(bytes([0x7F, MULTIPROTOCOL])) == [MULTIPROTOCOL]


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#4-own-code-not-listed')
def test_our_session_id_does_not_list_the_multisession_code() -> None:
    for neighbor in neighbours('capability { multi-session enable; }'):
        (value,) = Capabilities().new(neighbor, False)[MULTISESSION].extract_capability_bytes()
        assert MULTISESSION not in value[1:]
        assert Capability.CODE.MULTISESSION_CISCO not in value[1:]


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#4-own-code-not-listed', polarity='negative')
def test_the_multisession_code_in_a_received_session_id_is_ignored() -> None:
    assert session_id(bytes([0x00, MULTISESSION, MULTIPROTOCOL])) == [MULTIPROTOCOL]


def test_a_zero_length_value_is_refused_with_open_message_error() -> None:
    """Section 4 infers the Session Id length as the capability length minus one, so a zero
    length value does not follow the encoding.  No sentence says MUST about it, so this test
    names no requirement, but input which does not follow the encoding gets Notify(2, 0).
    """
    with pytest.raises(Notify) as raised:
        received(ipv4_unicast(), (MULTISESSION, b''))

    assert (raised.value.code, raised.value.subcode) == (2, 0)


def test_a_real_cisco_open_decodes_its_multisession_capability() -> None:
    """Cisco's code 131 value, as a Cisco router sent it: the flags octet and nothing
    after it, which this class reads as an empty Session Id.  It is not a zero length
    value, so refusing one with Notify(2, 0) does not refuse a Cisco router.
    """
    message = Message.unpack(int(Message.CODE.OPEN), CISCO_OPEN_BODY, Negotiated.UNSET)

    assert isinstance(message, Open)
    capability = message.capabilities[Capability.CODE.MULTISESSION_CISCO]
    assert isinstance(capability, MultiSession)
    assert list(capability) == []
    assert not message.capabilities.announced(MULTISESSION)


# ==============================================================================
# Negotiation
# ==============================================================================


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#7-session-id-mismatch-is-a-grouping-conflict')
def test_a_peer_with_our_session_id_is_accepted() -> None:
    assert negotiate(ours(), received(ipv4_unicast(), (MULTISESSION, bytes([0x00, MULTIPROTOCOL])))) is True


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#5-use-the-new-subcodes')
@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#7-session-id-mismatch-is-a-grouping-conflict', polarity='negative')
def test_a_peer_with_another_session_id_is_a_grouping_conflict() -> None:
    recv = received(ipv4_unicast(), (MULTISESSION, bytes([0x00, Capability.CODE.ROUTE_REFRESH])))

    result = negotiate(ours(), recv)

    assert isinstance(result, tuple)
    assert result[:2] == (2, 8)


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#7-no-matching-group-is-a-grouping-conflict')
def test_a_peer_whose_families_match_ours_is_accepted() -> None:
    assert negotiate(ours(), received(ipv4_unicast(), (MULTISESSION, bytes([0x00])))) is True


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#7-no-matching-group-is-a-grouping-conflict', polarity='negative')
def test_a_peer_whose_families_differ_from_ours_is_a_grouping_conflict() -> None:
    ipv6 = multiprotocol((AFI.ipv6, SAFI.unicast)).extract_capability_bytes()[0]

    result = negotiate(ours(), received((MULTIPROTOCOL, ipv6), (MULTISESSION, bytes([0x00, MULTIPROTOCOL]))))

    assert isinstance(result, tuple)
    assert result[:2] == (2, 8)


@pytest.mark.rfc('draft-ietf-idr-bgp-multisession-07#11-required-multisession-refuses-a-peer-without-it')
def test_a_peer_which_announces_multisession_is_not_refused_for_lacking_it() -> None:
    assert negotiate(ours(), received(ipv4_unicast(), (MULTISESSION, bytes([0x00])))) is True


@pytest.mark.rfc(
    'draft-ietf-idr-bgp-multisession-07#11-required-multisession-refuses-a-peer-without-it', polarity='negative'
)
def test_a_peer_without_multisession_is_refused_with_grouping_required() -> None:
    result = negotiate(ours(), received(ipv4_unicast()))

    assert isinstance(result, tuple)
    assert result[:2] == (2, 9)
