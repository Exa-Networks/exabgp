"""sr_policy/__init__.py

SR Policy Tunnel Type TLV (type 15, RFC 9012 / RFC 9256).

This module implements the SR Policy Tunnel Type (15) as a TunnelTypeTLV
subclass. The value of this tunnel TLV contains SR Policy Sub-TLVs.

Sub-TLVs supported:
  12  Preference
  13  Binding SID (MPLS)
  15  Priority
  20  SRv6 Binding SID
  128 Segment List
  129 Policy Name
  130 Candidate Path Name
"""

from __future__ import annotations

from typing import Any, ClassVar

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV, TunnelTypeTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.preference import PreferenceSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.priority import PrioritySubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.policy_name import PolicyNameSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.candidate_path_name import CandidatePathNameSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.binding_sid import BindingSIDSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.srv6_binding_sid import SRv6BindingSIDSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.segment_list import SegmentListSubTLV

# Type alias for buffer (bytes or bytearray)
Buffer = bytes | bytearray

_SR_POLICY_TUNNEL_TYPE = 15

__all__ = [
    'SRPolicyTunnel',
    'PreferenceSubTLV',
    'PrioritySubTLV',
    'PolicyNameSubTLV',
    'CandidatePathNameSubTLV',
    'BindingSIDSubTLV',
    'SRv6BindingSIDSubTLV',
    'SegmentListSubTLV',
]


@TunnelTypeTLV.register(_SR_POLICY_TUNNEL_TYPE)
class SRPolicyTunnel(TunnelTypeTLV):
    """SR Policy Tunnel Type TLV (type 15).

    Contains a list of SR Policy Sub-TLVs. Multiple Segment List Sub-TLVs
    are supported (each with its own weight).
    """

    TUNNEL_TYPE: ClassVar[int] = _SR_POLICY_TUNNEL_TYPE

    def __init__(self, subtlvs: list[Any]) -> None:
        self.subtlvs = subtlvs

    def pack_value(self) -> bytes:
        return b''.join(tlv.pack() for tlv in self.subtlvs)

    def json(self) -> str:
        parts: list[str] = []
        # Collect segment lists separately to emit as array
        segment_lists: list[str] = []
        for tlv in self.subtlvs:
            if isinstance(tlv, SegmentListSubTLV):
                segment_lists.append(tlv.json())
            else:
                parts.append(tlv.json())
        if segment_lists:
            parts.append('"segment-lists": [' + ', '.join(segment_lists) + ']')
        return '"sr-policy": {' + ', '.join(parts) + '}'

    def __str__(self) -> str:
        return 'sr-policy {' + ' '.join(str(t) for t in self.subtlvs) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SRPolicyTunnel:
        subtlvs = SubTLV.unpack_subtlvs(data)
        return cls(subtlvs=subtlvs)
