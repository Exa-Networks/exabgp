"""The effective local ASN survives OPEN's AS_TRANS representation."""

from unittest.mock import AsyncMock, Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.open.capability import ASN4, Capabilities, Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.neighbor import Neighbor
from exabgp.reactor.protocol import Protocol
from exabgp.util.enumeration import TriState


def negotiate(local: int, remote: int, advertise_asn4: bool, receive_asn4: bool) -> Negotiated:
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(local)
    neighbor.session.peer_as = ASN(remote)
    sent = Capabilities()
    received = Capabilities()
    if advertise_asn4:
        sent[Capability.CODE.FOUR_BYTES_ASN] = ASN4(local)
    if receive_asn4:
        received[Capability.CODE.FOUR_BYTES_ASN] = ASN4(remote)
    negotiated = Negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(local), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(remote), HoldTime(90), RouterID('192.0.2.2'), received))
    return negotiated


def test_four_octet_local_as_requires_asn4_advertisement() -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65537)
    neighbor.capability.asn4 = TriState.FALSE
    with pytest.raises(ValueError):
        Capabilities().new(neighbor, False)


@pytest.mark.parametrize('asn4', [TriState.TRUE, TriState.FALSE])
def test_unresolved_as_trans_is_rejected_during_open_generation(asn4: TriState) -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = AS_TRANS
    neighbor.capability.asn4 = asn4
    with pytest.raises(ValueError):
        Capabilities().new(neighbor, False)


def test_effective_open_asn_is_used_without_mutating_configured_auto_asn() -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(0)
    neighbor.capability.asn4 = TriState.TRUE
    capabilities = Capabilities().new(neighbor, False, local_as=ASN(65537))
    decoded = Capabilities.unpack(capabilities.pack_capabilities())
    assert int(decoded[Capability.CODE.FOUR_BYTES_ASN]) == 65537
    assert neighbor.session.local_as == 0


def test_effective_four_octet_as_requires_asn4_advertisement() -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(0)
    neighbor.capability.asn4 = TriState.FALSE
    with pytest.raises(ValueError):
        Capabilities().new(neighbor, False, local_as=ASN(65537))


@pytest.mark.asyncio
@pytest.mark.parametrize('remote_as', [65002, 70000])
async def test_auto_as_open_advertises_effective_asn_on_wire(remote_as: int) -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(0)
    neighbor.session.router_id = RouterID('192.0.2.1')
    neighbor.capability.asn4 = TriState.TRUE
    proto = Protocol(Mock(neighbor=neighbor, _restarted=False, stats={'send-open': 0}))
    proto.connection = Mock(writer_async=AsyncMock(), session=Mock(return_value='test'))
    received = Capabilities()
    received[Capability.CODE.FOUR_BYTES_ASN] = ASN4(remote_as)
    remote = Open.make_open(Version(4), ASN(remote_as), HoldTime(90), RouterID('192.0.2.2'), received)
    proto.negotiated.received(remote)

    await proto.new_open()

    wire = proto.connection.writer_async.await_args.args[0]
    decoded = Open.unpack_message(wire[19:], Negotiated.UNSET)
    assert decoded.asn == ASN(remote_as).trans()
    assert int(decoded.capabilities[Capability.CODE.FOUR_BYTES_ASN]) == remote_as
    assert neighbor.session.local_as == 0


def test_four_octet_ibgp_does_not_prepend_or_remove_local_preference() -> None:
    negotiated = negotiate(65537, 65537, True, True)
    assert negotiated.is_ibgp
    decoded = AttributeCollection.unpack(AttributeCollection().pack_attribute(negotiated), negotiated)
    path = decoded[ASPath.ID]
    assert isinstance(path, ASPath)
    assert path.aspath == ()
    assert LocalPreference.ID in decoded


def test_two_octet_local_as_is_not_replaced_by_peer_as() -> None:
    negotiated = negotiate(65001, 65002, False, False)
    assert not negotiated.is_ibgp
    decoded = AttributeCollection.unpack(AttributeCollection().pack_attribute(negotiated), negotiated)
    path = decoded[ASPath.ID]
    assert isinstance(path, ASPath)
    assert path.aspath == (SEQUENCE([ASN(65001)]),)


def test_automatic_local_as_keeps_the_identity_selected_for_open() -> None:
    neighbor = Neighbor()
    neighbor.session.peer_as = ASN(65002)
    negotiated = Negotiated(neighbor, Direction.OUT)
    sent = Capabilities().new(neighbor, False)
    negotiated.sent(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), Capabilities()))
    assert negotiated.local_as == 65002
    assert negotiated.is_ibgp


def test_numeric_peer_asn4_passes_open_validation() -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.session.peer_as = ASN(65537)
    sent = Capabilities()
    sent[Capability.CODE.FOUR_BYTES_ASN] = ASN4(65001)
    received = Capabilities()
    received[Capability.CODE.FOUR_BYTES_ASN] = 65537
    negotiated = Negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65537), HoldTime(90), RouterID('192.0.2.2'), received))
    assert negotiated.validate(neighbor) is None
    assert negotiated.peer_as.pack_asn(True) == b'\x00\x01\x00\x01'


@pytest.mark.parametrize('receive_asn4', [True, False])
def test_numeric_local_asn4_recovers_identity_without_requiring_peer_support(receive_asn4: bool) -> None:
    neighbor = Neighbor()
    neighbor.session.peer_as = ASN(65002)
    sent = Capabilities()
    sent[Capability.CODE.FOUR_BYTES_ASN] = 65537
    received = Capabilities()
    if receive_asn4:
        received[Capability.CODE.FOUR_BYTES_ASN] = ASN4(65002)
    negotiated = Negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(65537), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), received))
    assert negotiated.local_as.pack_asn(True) == b'\x00\x01\x00\x01'
    assert negotiated.asn4 is receive_asn4
    assert not negotiated.is_ibgp


@pytest.mark.parametrize('receive_asn4', [True, False])
def test_four_octet_local_as_survives_default_path_serialization(receive_asn4: bool) -> None:
    negotiated = negotiate(65537, 65002, True, receive_asn4)
    assert negotiated.local_as == 65537
    packed = AttributeCollection().pack_attribute(negotiated)
    decoded = AttributeCollection.unpack(packed, negotiated)
    path = decoded[ASPath.ID]
    assert isinstance(path, ASPath)
    assert path.aspath == (SEQUENCE([ASN(65537)]),)


def test_numeric_local_asn4_preserves_default_path_without_peer_support() -> None:
    neighbor = Neighbor()
    neighbor.session.peer_as = ASN(65002)
    sent = Capabilities()
    sent[Capability.CODE.FOUR_BYTES_ASN] = 65537
    negotiated = Negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(65537), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), Capabilities()))
    decoded = AttributeCollection.unpack(AttributeCollection().pack_attribute(negotiated), negotiated)
    path = decoded[ASPath.ID]
    assert isinstance(path, ASPath)
    assert path.aspath == (SEQUENCE([ASN(65537)]),)
