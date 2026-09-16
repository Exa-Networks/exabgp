"""The effective local ASN survives OPEN's AS_TRANS representation."""

from unittest.mock import AsyncMock, Mock

import pytest

from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.open.capability import ASN4, Capabilities, Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.reactor.protocol import Protocol
from exabgp.util.enumeration import TriState


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
