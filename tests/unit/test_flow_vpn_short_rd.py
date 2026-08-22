"""A flow_vpn NLRI shorter than its mandatory 8-byte Route Distinguisher parsed as filter rules.

SAFI.flow_vpn (RFC 4364-style VPN FlowSpec) carries a mandatory 8-byte RD before the rule
bytes. The stripping code in Flow._parse_rules was `if self.safi in (SAFI.flow_vpn,) and
len(bgp) >= 8: bgp = bgp[8:]` -- when the payload was shorter than 8 bytes the strip was
skipped and whatever bytes were meant to be the RD were fed straight into the rule parser
instead. A 3-byte payload [0x03, 0x81, 0x06] (component 3 "protocol", operator 0x81 EQ +
end-of-list, value 0x06 == TCP) decoded as a plausible-looking "flow protocol =tcp" rule
with a blank (NORD) RD: the peer's bytes silently became a traffic filter nobody sent,
instead of being refused.

Tested by driving Flow.unpack_nlri -- the peer-facing wire entry point -- and asserting
`nlri is NLRI.INVALID`. unpack_nlri wraps its parse in try/except Notify/ValueError/
IndexError and converts a Notify into the NLRI.INVALID sentinel rather than letting it
propagate, so a pytest.raises(Notify) test driven through unpack_nlri would fail even
against a correct fix -- INVALID is the observable peer-facing effect of the fix.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI


def decode_vpn(payload: bytes) -> NLRI:
    """Wrap payload with its wire length prefix and decode as flow_vpn."""
    data = bytes([len(payload)]) + payload
    nlri, _ = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_vpn, data, Action.ANNOUNCE, None, None)
    return nlri


# -- the whole 0..7 range is short of the mandatory 8-byte RD ----------------

# Bytes that, misread as rule bytes past a skipped RD strip, decode as a plausible
# component 3 (protocol) EQ TCP rule when exactly 3 of them are present.
RD_SHAPED_BYTES = bytes([0x03, 0x81, 0x06, 0x00, 0x00, 0x00, 0x00])


@pytest.mark.parametrize('length', range(8))
def test_flow_vpn_payload_shorter_than_rd_is_rejected(length: int) -> None:
    payload = RD_SHAPED_BYTES[:length]
    assert decode_vpn(payload) is NLRI.INVALID


def test_flow_vpn_three_byte_payload_no_longer_becomes_a_fake_protocol_rule() -> None:
    """The exact probe from the finding: RD bytes must not be read as a filter rule."""
    nlri, _ = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_vpn, bytes([0x03, 0x03, 0x81, 0x06]), Action.ANNOUNCE, None, None)
    assert nlri is NLRI.INVALID


# -- negative space: a fix that rejects all flow_vpn NLRI must not pass ------


def test_flow_vpn_with_full_rd_and_a_rule_still_decodes() -> None:
    """An 8-byte RD followed by one real component must still decode, with its RD intact."""
    # RD type 0 (2-byte AS admin): AS 100, assigned number 1 -> "100:1"
    rd = bytes([0x00, 0x00, 0x00, 0x64, 0x00, 0x00, 0x00, 0x01])
    rule = bytes([0x03, 0x81, 0x06])  # protocol == TCP, end of list
    nlri = decode_vpn(rd + rule)
    assert nlri is not NLRI.INVALID
    assert nlri.rd == RouteDistinguisher(rd)
    assert '100:1' in str(nlri.rd)
    assert 'protocol' in nlri.json()


def test_plain_flow_ip_three_byte_payload_is_unaffected() -> None:
    """SAFI.flow (non-VPN) has no RD to strip; the new check must not touch it."""
    nlri, _ = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_ip, bytes([0x03, 0x03, 0x81, 0x06]), Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID
    assert 'protocol' in nlri.json()
