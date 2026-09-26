"""RFC 4684 section 6: the End-of-RIB for RT membership, sent without graceful restart.

"implementations SHOULD generate an End-of-RIB marker ... for the Route Target membership
(afi, safi), regardless of whether graceful-restart is enabled on the BGP session." exabgp sends
one for every negotiated family, so the test is that (1, 132) is one of them, on a session with
graceful restart off, and that the marker is the RFC 4724 form for that family.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from exabgp.protocol.family import AFI, SAFI

# RFC 4724 2: an End-of-RIB for a family other than IPv4 unicast is an UPDATE holding only an
# empty MP_UNREACH_NLRI for that family
RTC_END_OF_RIB = bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E0200000007900F0003000184')


@pytest.fixture
def protocol() -> Any:
    from exabgp.reactor.protocol import Protocol

    neighbor = MagicMock()
    neighbor.capability.graceful_restart.is_enabled = Mock(return_value=False)
    peer = Mock()
    peer.neighbor = neighbor
    peer.stats = defaultdict(int)
    proto = Protocol(peer)
    proto.connection = Mock()
    proto.connection.writer_async = AsyncMock()
    proto.connection.session = Mock(return_value='test-session')
    return proto


@pytest.mark.rfc('rfc4684#6-end-of-rib-for-rt-membership')
@pytest.mark.asyncio
async def test_rt_membership_gets_its_end_of_rib_without_graceful_restart(protocol: Any) -> None:
    protocol.negotiated.families = [(AFI.ipv4, SAFI.mpls_vpn), (AFI.ipv4, SAFI.rtc)]

    await protocol.new_eors()

    written = [bytes(call.args[0]) for call in protocol.connection.writer_async.call_args_list]
    assert RTC_END_OF_RIB in written, [w.hex().upper() for w in written]
