"""sr_policy/__init__.py

SR Policy Tunnel Type TLV (type 15, RFC 9012 / RFC 9256).

This module implements the SR Policy Tunnel Type (15) as a TunnelTypeTLV
subclass. The value of this tunnel TLV contains SR Policy Sub-TLVs.

Sub-TLVs supported:
  12  Preference
  13  Binding SID (MPLS)
  14  ENLP (Explicit NULL Label Policy)
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
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.enlp import ENLPSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.priority import PrioritySubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.policy_name import PolicyNameSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.candidate_path_name import CandidatePathNameSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.binding_sid import BindingSIDSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.srv6_binding_sid import SRv6BindingSIDSubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.segment_list import SegmentListSubTLV
from exabgp.util.types import Buffer

_SR_POLICY_TUNNEL_TYPE = 15

# RFC 9830 sections 2.4.1, 2.4.2, 2.4.5, 2.4.6, 2.4.9 and 2.4.10 each say of one of these
# sub-TLVs that it "MUST NOT appear more than once in the SR Policy encoding", and RFC 9012
# section 13 says what a receiver does about a repeat: "all but the first occurrence of
# each such sub-TLV type MUST be disregarded.  However, the Tunnel TLV containing them
# MUST NOT be considered to be malformed, and all the sub-TLVs MUST be propagated if the
# route carrying the Tunnel Encapsulation attribute is propagated."  So the repeat is
# disregarded here, in json(), and nowhere else: pack_value() still emits every sub-TLV.
# Segment List (128) and SRv6 Binding SID (20) are absent on purpose, RFC 9830 lets both
# repeat, and the SRv6 Binding SID sentence says so in as many words.
_SINGLE_OCCURRENCE_SUBTLVS: frozenset[int] = frozenset(
    (
        PreferenceSubTLV.SUBTYPE,
        BindingSIDSubTLV.SUBTYPE,
        ENLPSubTLV.SUBTYPE,
        PrioritySubTLV.SUBTYPE,
        CandidatePathNameSubTLV.SUBTYPE,
        PolicyNameSubTLV.SUBTYPE,
    )
)

__all__ = [
    'SRPolicyTunnel',
    'ENLPSubTLV',
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
        emitted: set[int] = set()
        for tlv in self.subtlvs:
            if tlv.SUBTYPE in _SINGLE_OCCURRENCE_SUBTLVS:
                # RFC 9012 13: all but the first occurrence is disregarded.  Emitting both
                # put the same key in one object twice and left the consumer's parser to
                # decide which one won, which is not a decision a parser should be making.
                if tlv.SUBTYPE in emitted:
                    continue
                emitted.add(tlv.SUBTYPE)
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
