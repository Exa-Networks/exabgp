"""OPEN advertises the resolved identity without changing automatic-AS configuration."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from exabgp.bgp.message import Message, Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.open.capability import ASN4, Capabilities, Capability
from exabgp.bgp.neighbor import Neighbor
from exabgp.reactor.protocol import Protocol


class RecordingConnection:
    def __init__(self):
        self.messages = []

    def writer(self, raw):
        self.messages.append(raw)
        yield True

    def session(self):
        return 'test-effective-asn'


def _neighbor(local_as=None, asn4=True):
    neighbor = Neighbor()
    neighbor['local-as'] = local_as
    neighbor['router-id'] = RouterID('192.0.2.1')
    neighbor['capability']['asn4'] = asn4
    neighbor.api = {}
    return neighbor


def _received_open(header_asn, capability_asn=None):
    capabilities = Capabilities()
    if capability_asn is not None:
        capabilities[Capability.CODE.FOUR_BYTES_ASN] = ASN4(capability_asn)
    message = Open(Version(4), ASN(header_asn), HoldTime(90), RouterID('192.0.2.2'), capabilities)
    return Open.unpack_message(message.message()[Message.HEADER_LEN :])


@pytest.fixture
def protocol_factory(monkeypatch):
    monkeypatch.setattr('exabgp.reactor.protocol.log.debug', lambda *args: None)

    def make(neighbor, received=None):
        peer = SimpleNamespace(neighbor=neighbor, _restarted=False, stats={'send-open': 0})
        protocol = Protocol(peer)
        protocol.connection = RecordingConnection()
        if received is not None:
            protocol.negotiated.received(received)
        return protocol

    return make


@pytest.mark.parametrize(
    'header_asn,capability_asn,effective_asn',
    [(65002, None, 65002), (65002, 65002, 65002), (AS_TRANS, 70000, 70000), (65002, 70000, 65002)],
)
def test_auto_open_advertises_peer_identity(protocol_factory, header_asn, capability_asn, effective_asn):
    neighbor = _neighbor()
    before = deepcopy(dict(neighbor))
    protocol = protocol_factory(neighbor, _received_open(header_asn, capability_asn))

    sent = list(protocol.new_open())[-1]

    (wire,) = protocol.connection.messages
    decoded = Open.unpack_message(wire[Message.HEADER_LEN :])
    assert decoded.asn == ASN(effective_asn).trans()
    assert decoded.capabilities[Capability.CODE.FOUR_BYTES_ASN] == effective_asn
    protocol.negotiated.sent(sent)
    assert protocol.negotiated.local_as == effective_asn
    assert dict(neighbor) == before


def test_configured_four_octet_identity_survives_open_wire(protocol_factory):
    neighbor = _neighbor(ASN(65537))
    protocol = protocol_factory(neighbor)

    sent = list(protocol.new_open())[-1]

    (wire,) = protocol.connection.messages
    decoded = Open.unpack_message(wire[Message.HEADER_LEN :])
    assert decoded.asn == AS_TRANS
    assert decoded.capabilities[Capability.CODE.FOUR_BYTES_ASN] == 65537
    protocol.negotiated.sent(sent)
    protocol.negotiated.received(_received_open(65002, 65002))
    assert protocol.negotiated.local_as == 65537
    assert neighbor['local-as'] == 65537


def test_auto_two_octet_identity_without_asn4_advertisement(protocol_factory):
    neighbor = _neighbor(asn4=False)
    protocol = protocol_factory(neighbor, _received_open(65002))

    list(protocol.new_open())

    (wire,) = protocol.connection.messages
    decoded = Open.unpack_message(wire[Message.HEADER_LEN :])
    assert decoded.asn == 65002
    assert Capability.CODE.FOUR_BYTES_ASN not in decoded.capabilities
    assert neighbor['local-as'] is None


def test_capability_override_controls_wire_without_mutating_configuration():
    neighbor = _neighbor(ASN(65001))
    before = deepcopy(dict(neighbor))

    capabilities = Capabilities().new(neighbor, False, local_as=ASN(65537))

    decoded = Capabilities.unpack(capabilities.pack())
    assert decoded[Capability.CODE.FOUR_BYTES_ASN] == 65537
    assert dict(neighbor) == before


@pytest.mark.parametrize(
    'local_as,asn4', [(None, True), (None, False), (AS_TRANS, True), (AS_TRANS, False), (ASN(65537), False)]
)
def test_capabilities_reject_unadvertisable_configured_identity(local_as, asn4):
    with pytest.raises(ValueError):
        Capabilities().new(_neighbor(local_as, asn4), False)


@pytest.mark.parametrize('effective_asn,asn4', [(AS_TRANS, True), (AS_TRANS, False), (ASN(65537), False)])
def test_capabilities_reject_unadvertisable_override(effective_asn, asn4):
    with pytest.raises(ValueError):
        Capabilities().new(_neighbor(ASN(65001), asn4), False, local_as=effective_asn)


@pytest.mark.parametrize(
    'local_as,asn4,received',
    [
        (None, True, None),
        (None, True, _received_open(AS_TRANS)),
        (None, True, _received_open(AS_TRANS, AS_TRANS)),
        (None, False, _received_open(AS_TRANS, 70000)),
        (ASN(65537), False, None),
        (AS_TRANS, True, None),
    ],
)
def test_invalid_local_identity_uses_reactor_notification_boundary(protocol_factory, local_as, asn4, received):
    neighbor = _neighbor(local_as, asn4)
    before = deepcopy(dict(neighbor))
    protocol = protocol_factory(neighbor, received)

    with pytest.raises(Notify) as caught:
        list(protocol.new_open())

    assert (caught.value.code, caught.value.subcode) == (6, 0)
    assert protocol.connection.messages == []
    assert dict(neighbor) == before
