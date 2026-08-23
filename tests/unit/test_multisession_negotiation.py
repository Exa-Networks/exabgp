#!/usr/bin/env python3
# encoding: utf-8
"""test_multisession_negotiation.py

Regression tests for F7: MultiSession.unpack_capability ignored its `data`
argument entirely, so a peer's MULTISESSION/MULTISESSION_CISCO capability was
always unpacked into an empty session-id list, no matter what the peer sent.

In negotiated.py, an empty received session-id set is replaced by the
hardcoded default `{MULTIPROTOCOL}` -- the only set ExaBGP itself ever sends
(capabilities.py:_session) -- so the received set always equaled the sent
set and the `self.multisession = (2, 8, ...)` refusal branch was
structurally unreachable: a peer echoing a different session-id set was
silently accepted instead of being refused.

Created for ExaBGP testing framework
License: 3-clause BSD
"""

from unittest.mock import Mock

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import ASN, HoldTime, RouterID, Version
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.capabilities import Parameter
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.protocol.family import AFI, SAFI


# ==============================================================================
# Helpers
# ==============================================================================


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated.make_negotiated(neighbor, Direction.OUT)


def pack_open_parameters(entries: list[tuple[int, bytes]]) -> bytes:
    """Build a genuine OPEN optional-parameters buffer, the kind Capabilities.unpack
    consumes, out of (capability code, capability value) pairs -- one Capabilities
    (type 2) parameter wrapping all of them, mirroring the TLV layout Capabilities.pack_capabilities()
    itself produces (see capabilities.py).
    """
    capability_tlvs = b''.join(bytes([code, len(value)]) + value for code, value in entries)
    parameter = bytes([Parameter.CAPABILITIES, len(capability_tlvs)]) + capability_tlvs
    return bytes([len(parameter)]) + parameter


def make_multiprotocol_capability() -> MultiProtocol:
    mp = MultiProtocol()
    mp.append((AFI.ipv4, SAFI.unicast))
    return mp


# ==============================================================================
# (a) unpack_capability populates the instance list
# ==============================================================================


def test_multisession_unpack_capability_direct_call() -> None:
    """A payload of concatenated 1-octet capability codes populates the instance
    list in wire order -- the actual F7 bug: unpack_capability() ignored `data`
    entirely, so this list stayed empty regardless of what a peer sent.
    """
    instance = MultiSession()
    data = bytes([Capability.CODE.MULTIPROTOCOL, Capability.CODE.ROUTE_REFRESH, Capability.CODE.FOUR_BYTES_ASN])

    result = MultiSession.unpack_capability(instance, data, Capability.CODE.MULTISESSION)

    assert result is instance
    assert list(result) == [
        Capability.CODE.MULTIPROTOCOL,
        Capability.CODE.ROUTE_REFRESH,
        Capability.CODE.FOUR_BYTES_ASN,
    ]


def test_multisession_unpack_capability_via_capabilities_unpack() -> None:
    """End-to-end through Capabilities.unpack() on a genuine OPEN optional-parameters
    buffer carrying a single MULTISESSION capability TLV with a 3-byte session-id
    payload -- this is the shape a real peer's OPEN message takes on the wire.
    """
    payload = bytes([Capability.CODE.MULTIPROTOCOL, Capability.CODE.ROUTE_REFRESH, Capability.CODE.FOUR_BYTES_ASN])
    wire = pack_open_parameters([(Capability.CODE.MULTISESSION, payload)])

    capabilities = Capabilities.unpack(wire)

    ms = capabilities[Capability.CODE.MULTISESSION]
    assert isinstance(ms, MultiSession)
    assert list(ms) == [
        Capability.CODE.MULTIPROTOCOL,
        Capability.CODE.ROUTE_REFRESH,
        Capability.CODE.FOUR_BYTES_ASN,
    ]


def test_multisession_pack_unpack_round_trip_recovers_original_set() -> None:
    """set(X) -> pack_capabilities() -> Capabilities.unpack() must recover exactly X.

    MultiSession.extract_capability_bytes() always prepends a bytes([0]) placeholder
    ahead of the real session-id bytes, and Capabilities.pack_capabilities() turns
    every list element it returns -- the placeholder included -- into its own
    capability TLV under the same code; Capability.unpack() folds every TLV for a
    given code into the *same* instance via capabilities.get(). A naive fix that
    appends every byte, including that leading placeholder, would make ExaBGP's own
    {MULTIPROTOCOL} session-id set come back as {RESERVED, MULTIPROTOCOL} -- and two
    ExaBGP peers with multi-session enabled could never agree with each other. 0x00
    is CapabilityCode.RESERVED, never a real session id .set() adds, so it must be
    skipped on unpack for the round trip to be exact.
    """
    caps = Capabilities()
    caps[Capability.CODE.MULTIPROTOCOL] = make_multiprotocol_capability()
    caps[Capability.CODE.MULTISESSION] = MultiSession().set([Capability.CODE.MULTIPROTOCOL])

    wire = caps.pack_capabilities()
    recovered = Capabilities.unpack(wire)

    assert set(recovered[Capability.CODE.MULTISESSION]) == {Capability.CODE.MULTIPROTOCOL}


# ==============================================================================
# (b) Negotiated.multisession refuses a peer whose session-id set differs
# ==============================================================================


def test_negotiated_multisession_refusal_on_session_id_mismatch() -> None:
    """A peer that echoes a session-id set different from ours must be refused
    with the (2, 8, ...) NOTIFICATION tuple, not silently accepted.

    Our side is built the way capabilities.py:_session() builds it (.set() is
    never round-tripped through unpack -- it is our own outgoing message). The
    peer's side is parsed from a genuine wire buffer, the only path that ever
    exercised the F7 bug.
    """
    sent_caps = Capabilities()
    sent_caps[Capability.CODE.MULTIPROTOCOL] = make_multiprotocol_capability()
    sent_caps[Capability.CODE.MULTISESSION] = MultiSession().set([Capability.CODE.MULTIPROTOCOL])

    peer_caps = Capabilities()
    peer_caps[Capability.CODE.MULTIPROTOCOL] = make_multiprotocol_capability()
    peer_caps[Capability.CODE.MULTISESSION] = MultiSession().set([Capability.CODE.ROUTE_REFRESH])
    recv_caps = Capabilities.unpack(peer_caps.pack_capabilities())

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    negotiated = create_negotiated()
    negotiated.sent(sent_open)
    negotiated.received(recv_open)

    assert negotiated.multisession == (2, 8, 'multisession, our peer did not reply with the same sessionid')


# ==============================================================================
# (c) Negative space
# ==============================================================================


def test_negotiated_multisession_absent_stays_false() -> None:
    """With no MULTISESSION capability on either side, multisession stays the
    plain `False` default and nothing new fires.
    """
    sent_caps = Capabilities()
    sent_caps[Capability.CODE.MULTIPROTOCOL] = make_multiprotocol_capability()

    recv_caps = Capabilities()
    recv_caps[Capability.CODE.MULTIPROTOCOL] = make_multiprotocol_capability()

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    negotiated = create_negotiated()
    negotiated.sent(sent_open)
    negotiated.received(recv_open)

    assert negotiated.multisession is False


def test_negotiated_multisession_accepted_when_session_ids_match() -> None:
    """A peer echoing exactly our session-id set is accepted: multisession stays
    the plain `True` boolean, not the refusal tuple.
    """
    sent_caps = Capabilities()
    sent_caps[Capability.CODE.MULTIPROTOCOL] = make_multiprotocol_capability()
    sent_caps[Capability.CODE.MULTISESSION] = MultiSession().set([Capability.CODE.MULTIPROTOCOL])

    peer_caps = Capabilities()
    peer_caps[Capability.CODE.MULTIPROTOCOL] = make_multiprotocol_capability()
    peer_caps[Capability.CODE.MULTISESSION] = MultiSession().set([Capability.CODE.MULTIPROTOCOL])
    recv_caps = Capabilities.unpack(peer_caps.pack_capabilities())

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    negotiated = create_negotiated()
    negotiated.sent(sent_open)
    negotiated.received(recv_open)

    assert negotiated.multisession is True
