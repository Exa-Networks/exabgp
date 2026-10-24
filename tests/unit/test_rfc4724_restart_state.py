"""RFC 4724 4.2: only a speaker which has restarted may set the Restart State bit.

"In re-establishing the session, the 'Restart State' bit in the Graceful Restart
Capability of the OPEN message sent by the Receiving Speaker MUST NOT be set unless the
Receiving Speaker has restarted."

`Peer._restarted` was initialised to the module constant `FORCE_GRACEFUL`, which is True,
and only `stop()` ever cleared it, and `stop()` is the path where the peer is going away
for good.  So the bit was set on the first OPEN and on every reconnection for the life of
the process: a TCP reset, an expired hold timer, or a peer which itself restarted, after
months of uptime, all claimed our speaker had just come back.  The bit tells the peer not
to wait for our End-of-RIB before advertising to us, and the peer acts on it.

The first OPEN of a process still claims a restart, deliberately.  This run may be a
restart of an earlier one, in which case 4.1 requires the bit and a peer is holding our
routes; or it may be a genuine first start, in which case 4.2 forbids it.  Nothing on the
box distinguishes the two, because exabgp keeps no state between runs.  Setting it only
asks the peer not to wait, so it is the cheap way to be wrong.

`_establish()` now clears the flag once a session has been held.  `reestablish()`, which
backs the `restart` command and a reload which changed the neighbour, still sets it.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'
os.environ['exabgp_tcp_bind'] = '127.0.0.1'
os.environ['exabgp_tcp_attempts'] = '0'

from exabgp.bgp.fsm import FSM  # noqa: E402
from exabgp.bgp.message.open.asn import ASN  # noqa: E402
from exabgp.bgp.message.open.holdtime import HoldTime  # noqa: E402
from exabgp.bgp.message.open.routerid import RouterID  # noqa: E402
from exabgp.bgp.message.open.capability.capability import Capability  # noqa: E402
from exabgp.bgp.message.open.capability.capabilities import Capabilities  # noqa: E402
from exabgp.bgp.message.open.capability.graceful import Graceful  # noqa: E402
from exabgp.bgp.neighbor import Neighbor  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402
from exabgp.reactor.peer import ACTION, Peer  # noqa: E402

HOLD_TIME = 180

# _establish is a generator and every step below is stubbed, so it finishes in a handful
# of rounds; the bound is what stops a stub which never returns from hanging the suite
MAX_ESTABLISH_ROUNDS = 16


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """The peer logs each state change and no logger is configured under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


def neighbour() -> Neighbor:
    """A neighbour with graceful-restart on, which is what puts the capability in the OPEN."""
    neighbor = Neighbor()
    neighbor['local-as'] = ASN(65000)
    neighbor['peer-as'] = ASN(65001)
    neighbor['local-address'] = IP.create('192.0.2.2')
    neighbor['peer-address'] = IP.create('192.0.2.1')
    neighbor['router-id'] = RouterID('192.0.2.2')
    neighbor['hold-time'] = HoldTime(HOLD_TIME)
    neighbor['capability']['graceful-restart'] = HOLD_TIME
    # api and rib are filled in outside the class, and Peer reads both
    neighbor.api = {'neighbor-changes': False, 'fsm': False}
    neighbor.rib = Mock()
    return neighbor


def establish(peer: Peer) -> None:
    """Take a Peer to ESTABLISHED over a protocol which answers but sends nothing.

    The Restart State bit is decided by how many sessions this process has held with the
    neighbour, so a test about it has to go through the establishment path rather than poke
    the flag that path sets.
    """
    protocol = MagicMock()
    protocol.negotiated.holdtime = HOLD_TIME
    protocol.negotiated.msg_size = 4096
    peer.proto = protocol

    def one(value: Any) -> Any:
        def generator() -> Any:
            yield value

        return generator

    # every step but the flag is stubbed: the values yielded are not in ACTION.ALL, so
    # _establish reads them as the OPEN it sent and the OPEN it read and walks on
    peer._send_open = one(Mock())
    peer._read_open = one(Mock())
    peer._send_ka = one(ACTION.NOW)
    peer._read_ka = one(ACTION.NOW)

    rounds = 0
    for _ in peer._establish():
        rounds += 1
        assert rounds < MAX_ESTABLISH_ROUNDS, 'the stubbed establishment did not finish'

    assert peer.fsm == FSM.ESTABLISHED, 'the stubbed protocol did not reach ESTABLISHED'


def restart_state(peer: Peer) -> int:
    """The Restart State bit of the Graceful Restart capability we would send next."""

    capabilities = Capabilities().new(peer.neighbor, peer._restarted)
    graceful = capabilities[Capability.CODE.GRACEFUL_RESTART]
    assert isinstance(graceful, Graceful)
    return graceful.restart_flag & Graceful.RESTART_STATE


def test_the_first_open_of_a_process_claims_a_restart() -> None:
    """Deliberate, and the reason FORCE_GRACEFUL exists.

    This run may be a restart of an earlier one, in which case 4.1 requires the bit and a
    peer is holding our routes; or it may be a first start, in which case 4.2 forbids it.
    Nothing here can tell which, because exabgp keeps no state between runs.
    """
    peer = Peer(neighbour(), Mock())

    assert restart_state(peer), 'the first OPEN did not claim a restart'


def test_a_reconnecting_speaker_does_not_claim_it_has_restarted() -> None:
    """ "In re-establishing the session" is what 4.2 binds, and that case is knowable.

    Once this process has held a session with a neighbour, everything after it is a
    reconnection: a TCP reset, a hold timer, a peer which itself restarted. This speaker
    did not restart, and the bit tells the peer not to wait for our End-of-RIB.
    """
    peer = Peer(neighbour(), Mock())

    establish(peer)

    assert not restart_state(peer), 'a peer reconnecting within one process advertised the Restart State bit'


def test_an_operator_asking_for_a_restart_gets_the_bit_back() -> None:
    """reestablish() is the `restart` command and a reload which changed the neighbour.

    The session is torn down and the RIB rebuilt, so the peer is told rather than left to
    wait on an End-of-RIB for routes it is about to be sent again.
    """
    peer = Peer(neighbour(), Mock())
    establish(peer)

    peer.reestablish()

    assert restart_state(peer), 'an operator asked for a restart and the peer was not told'
