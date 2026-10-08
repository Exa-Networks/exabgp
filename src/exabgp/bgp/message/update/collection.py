"""update/collection.py - UpdateCollection semantic container

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import chain, islice
from struct import pack, unpack
from typing import TYPE_CHECKING, Generator, cast

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update import Update

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.update.attribute.otc import OTC
from exabgp.bgp.message.update.attribute import MPRNLRI, MPURNLRI, Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.aspath import CONFED_SEQUENCE, SEQUENCE, ASPath
from exabgp.bgp.message.update.attribute.attribute import Discard, TreatAsWithdraw
from exabgp.bgp.message.update.attribute.collection import (
    NEXT_HOP_IGNORED_ACTION,
    TREAT_AS_WITHDRAW_ACTION,
    in_type_order,
)
from exabgp.bgp.message.update.attribute.sr.labelindex import SrLabelIndex
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.nlri import NLRI, MPNLRICollection
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.qualifier import Labels, RouteDistinguisher
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP, IPv4, IPv6
from exabgp.bgp.message.update.attribute.nexthop import NextHop

# RFC 7606 6 asks for the NLRI involved and the entire malformed UPDATE in an error log. A
# peer sets the size of both, so each is capped: the NLRI by count, the message at the size
# of any message sent without RFC 8654 Extended Message, which it therefore holds whole.
MAX_LOGGED_NLRI = 16
MAX_LOGGED_UPDATE_OCTETS = Message.STANDARD_MAX


def validate_announce_nlri(nlri: 'NLRI', nexthop: IP) -> str | None:
    """Validate NLRI and nexthop for announcement.

    Returns error message if invalid, None if valid.

    This is the single source of truth for announce validation:
    - Called at wire format generation time (required for all routes)
    - Called at API level for early feedback (optional but better UX)

    Withdrawals don't need this validation (RFC 4271: MP_UNREACH_NLRI has no nexthop).
    """
    # 1. Nexthop validation - required for unicast/multicast announces
    if nlri.safi in (SAFI.unicast, SAFI.multicast):
        # Check for undefined nexthop (IP.NoNextHop has afi=AFI.undefined)
        if nexthop.afi == AFI.undefined:
            return f'announce requires nexthop: {nlri}'

    # 2. Labels validation - required for labeled route announces
    if nlri.safi.has_label():
        if isinstance(nlri, Label) and nlri.labels is Labels.NOLABEL:
            return f'labeled route announce requires labels: {nlri}'

    # 3. RD validation - required for VPN route announces
    if nlri.safi.has_rd():
        if isinstance(nlri, IPVPN) and nlri.rd is RouteDistinguisher.NORD:
            return f'VPN route announce requires RD: {nlri}'

    return None


# RFC 4271 6.3 names "an unexpected multicast IP address" as a semantically incorrect
# prefix, and 5.1.3 asks a NEXT_HOP to be an address a router can forward to: 224.0.0.0/4
# is neither, and 0.0.0.0 is no address at all.
MULTICAST_IPV4_FIRST_NIBBLE = 0xE
MULTICAST_IPV4_MASK_BITS = 4
UNSPECIFIED_IPV4 = bytes(4)


def _semantic_error(routed: 'RoutedNLRI') -> str | None:
    """What is semantically wrong with a route of the legacy NLRI field, or None."""
    nexthop = routed.nexthop
    if nexthop.afi == AFI.ipv4:
        packed = bytes(nexthop.pack_ip())
        if packed == UNSPECIFIED_IPV4:
            return f'NEXT_HOP {nexthop} is the unspecified address (RFC 4271 6.3)'
        if packed[0] >> 4 == MULTICAST_IPV4_FIRST_NIBBLE:
            return f'NEXT_HOP {nexthop} is a multicast address (RFC 4271 6.3)'
    nlri = routed.nlri
    if isinstance(nlri, INET) and nlri.afi == AFI.ipv4:
        cidr = nlri.cidr
        if cidr.mask >= MULTICAST_IPV4_MASK_BITS and cidr.pack_ip()[0] >> 4 == MULTICAST_IPV4_FIRST_NIBBLE:
            return f'prefix {nlri} is multicast (RFC 4271 6.3)'
    return None


def _withdraw_reason(nlri: 'NLRI', attributes: AttributeCollection, negotiated: Negotiated) -> str | None:
    """Why an announced route makes its whole UPDATE treat-as-withdraw, or None."""
    # RFC 8277 2.1: more labels than the Count we announced, or than one label when the
    # Multiple Labels Capability did not go both ways
    accepted = negotiated.labels_accepted(nlri.afi, nlri.safi)
    if nlri.label_count() > accepted:
        return f'{nlri.label_count()} labels bound to one prefix, more than the {accepted} we take (RFC 8277 2.1)'
    # RFC 9830 5: an SR Policy update which 4.2.1 does not call valid is treat-as-withdraw
    return nlri.malformed_with(attributes)


@dataclass(frozen=True, slots=True)
class RoutedNLRI:
    """NLRI with associated nexthop for wire format encoding.

    This is a lightweight immutable container used by UpdateCollection
    to group NLRIs with their nexthops for wire format generation.
    It does not include action (determined by list placement: announces vs withdraws)
    or attributes (handled separately by UpdateCollection).

    Using this instead of storing nexthop in NLRI allows NLRI to be immutable
    and reusable across different nexthop contexts.
    """

    nlri: NLRI
    nexthop: IP


@dataclass(frozen=True, slots=True)
class RouteLeak:
    peer_role: str
    peer_as: str
    expected_otc: str
    received_otc: str

    def as_dict(self) -> dict[str, str]:
        return {
            'reason': 'invalid-otc',
            'peer-role': self.peer_role,
            'peer-as': self.peer_as,
            'expected-otc': self.expected_otc,
            'received-otc': self.received_otc,
        }


# Update message header offsets and constants
UPDATE_WITHDRAWN_LENGTH_OFFSET = 2  # Offset to start of withdrawn routes
UPDATE_ATTR_LENGTH_HEADER_SIZE = 4  # Size of withdrawn length (2) + attr length (2)


# ======================================================================= UpdateCollection

# +-----------------------------------------------------+
# |   Withdrawn Routes Length (2 octets)                |
# +-----------------------------------------------------+
# |   Withdrawn Routes (variable)                       |
# +-----------------------------------------------------+
# |   Total Path Attribute Length (2 octets)            |
# +-----------------------------------------------------+
# |   Path Attributes (variable)                        |
# +-----------------------------------------------------+
# |   Network Layer Reachability Information (variable) |
# +-----------------------------------------------------+

# Withdrawn Routes:

# +---------------------------+
# |   Length (1 octet)        |
# +---------------------------+
# |   Prefix (variable)       |
# +---------------------------+


class UpdateCollection:
    """Semantic container for BGP UPDATE message data.

    Holds announces, withdraws, and attributes as semantic objects.
    Used as a builder to construct UPDATE messages from semantic data.

    Announces are stored as RoutedNLRI (nlri + nexthop) because nexthop
    is needed for MP_REACH_NLRI wire format encoding.

    Withdraws are stored as bare NLRI because MP_UNREACH_NLRI doesn't
    include nexthop.

    It is not a Message: it builds them.  messages() turns it into as many UPDATEs as
    its routes need, and Update.parse() turns an UPDATE back into one.

    An End-of-RIB (RFC 4724) is a collection with no route, marked with its family:
    make_eor() builds one, IS_EOR tells it apart, eor_afi and eor_safi name the family.
    """

    def __init__(
        self,
        announces: list[RoutedNLRI],
        withdraws: list[NLRI],
        attributes: AttributeCollection,
        eor: FamilyTuple | None = None,
    ) -> None:
        assert eor is None or not (announces or withdraws), 'an End-of-RIB carries no route'
        self._eor: FamilyTuple | None = eor
        # UpdateCollection is a composite container - NLRIs and Attributes are already packed-bytes-first
        # No single _packed representation exists because messages() can generate multiple
        # wire-format messages from one UpdateCollection due to size limits
        self._announces: list[RoutedNLRI] = announces
        self._withdraws: list[NLRI] = withdraws
        self._attributes: AttributeCollection = attributes
        self.route_leaks: dict[FamilyTuple, RouteLeak] | None = None

    def withhold(self, withheld: list[RoutedNLRI]) -> None:
        """Take announcements out of a received UPDATE before anything acts on it.

        RFC 8955 6: a flow specification which is not feasible is neither held in the
        adj-rib-in nor told to the API.
        """
        before = len(self._announces)
        # by identity: two announcements of one prefix compare equal, and only these go
        taken = {id(routed) for routed in withheld}
        self._announces = [routed for routed in self._announces if id(routed) not in taken]
        assert len(self._announces) == before - len(withheld), 'only announcements of this UPDATE are withheld'

    def classify_otc(self, negotiated: Negotiated) -> None:
        """Apply the ingress procedures of RFC 9234 5 to a received UPDATE.

        A route leak is recorded, not acted on. A route which should have arrived marked
        and did not is marked, on a copy of the attributes: the collection itself may be
        the one the session's attribute cache hands to the next UPDATE.
        """
        self.route_leaks = None
        self._mark_otc_on_ingress(negotiated)
        otc = self.attributes.get(Attribute.CODE.OTC)
        role = negotiated.peer_role
        if negotiated.role == RoleValue.NO_ROLE or not isinstance(otc, OTC):
            return
        if role not in (RoleValue.CUSTOMER, RoleValue.RS_CLIENT, RoleValue.PEER):
            return
        if role == RoleValue.PEER and otc.asn == negotiated.peer_as:
            return
        record = RouteLeak(
            str(role), f'AS{negotiated.peer_as}', 'peer-as' if role == RoleValue.PEER else 'none', f'AS{otc.asn}'
        )
        for routed in self.announces:
            family = routed.nlri.family().afi_safi()
            if family not in ((AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)):
                continue
            if self.route_leaks is None:
                self.route_leaks = {}
            self.route_leaks[family] = record
            assert len(self.route_leaks) <= 2, 'OTC procedures cover only IPv4 and IPv6 unicast'
            log.warning(
                lazymsg(
                    'update.otc.leak reason=invalid-otc neighbor={neighbor} peer-role={role} peer-as={asn} '
                    'expected-otc={expected} received-otc={received} family="{family}" prefix={prefix}',
                    neighbor=negotiated.neighbor.session.peer_address,
                    role=record.peer_role,
                    asn=record.peer_as,
                    expected=record.expected_otc,
                    received=record.received_otc,
                    family=routed.nlri.family(),
                    prefix=routed.nlri,
                ),
                'reactor',
            )

    def _mark_otc_on_ingress(self, negotiated: Negotiated) -> None:
        """RFC 9234 5 ingress rule 3: add the OTC a Provider, Peer or RS left off.

        "If a route is received from a Provider, a Peer, or an RS and the OTC Attribute is
        not present, then it MUST be added with a value equal to the AS number of the
        remote AS." Section 5 only covers IPv4 and IPv6 unicast, so an UPDATE announcing
        nothing in those families is left as it came.
        """
        if negotiated.role == RoleValue.NO_ROLE or Attribute.CODE.OTC in self._attributes:
            return
        if negotiated.peer_role not in (RoleValue.PROVIDER, RoleValue.PEER, RoleValue.RS):
            return
        unicast = ((AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast))
        if not any(routed.nlri.family().afi_safi() in unicast for routed in self._announces):
            return
        marked = self._attributes.copy()
        marked.add(OTC.make_otc(int(negotiated.peer_as)))
        self._attributes = marked

    @classmethod
    def make_eor(cls, afi: AFI, safi: SAFI) -> 'UpdateCollection':
        """The End-of-RIB marker of a family."""
        return cls([], [], AttributeCollection(), eor=(afi, safi))

    @property
    def IS_EOR(self) -> bool:
        """True if this is an End-of-RIB marker."""
        return self._eor is not None

    @property
    def eor_afi(self) -> AFI:
        """AFI of this EOR marker. Only call on EOR instances."""
        assert self._eor is not None, 'eor_afi called on non-EOR UpdateCollection'
        return self._eor[0]

    @property
    def eor_safi(self) -> SAFI:
        """SAFI of this EOR marker. Only call on EOR instances."""
        assert self._eor is not None, 'eor_safi called on non-EOR UpdateCollection'
        return self._eor[1]

    @property
    def nlris(self) -> list[NLRI]:
        """Every NLRI, announced then withdrawn; for an End-of-RIB, the one which names its family."""
        if self._eor is not None:
            from exabgp.bgp.message.update.eor import EOR

            return [EOR.EOR_NLRI(*self._eor)]
        return [routed.nlri for routed in self._announces] + self._withdraws

    @property
    def announces(self) -> list[RoutedNLRI]:
        return self._announces

    @property
    def withdraws(self) -> list[NLRI]:
        return self._withdraws

    @property
    def attributes(self) -> AttributeCollection:
        return self._attributes

    def get_nexthop(self) -> IP:
        """Get the nexthop IP from attributes (NEXT_HOP attribute).

        Returns the IP from the NEXT_HOP attribute if present,
        otherwise returns IP.NoNextHop.

        For MP routes, nexthop is in MP_REACH_NLRI, not NEXT_HOP attribute.
        """

        nexthop_attr = self._attributes.get(Attribute.CODE.NEXT_HOP, None)
        if nexthop_attr is None:
            return IP.NoNextHop
        # NextHop attribute - extract IP from packed bytes
        if isinstance(nexthop_attr, NextHop):
            packed = nexthop_attr._packed
        else:
            return IP.NoNextHop
        if len(packed) == IPv4.BYTES:
            return IPv4(packed)
        elif len(packed) == IPv6.BYTES:
            return IPv6(packed)
        return IP.NoNextHop

    # message not implemented we should use messages below.

    def __str__(self) -> str:
        return '\n'.join(['{}{}'.format(str(self.nlris[n]), str(self.attributes)) for n in range(len(self.nlris))])

    @staticmethod
    def prefix(data: Buffer) -> bytes:
        # This function needs renaming
        return pack('!H', len(data)) + data

    @staticmethod
    def split(data: Buffer) -> tuple[Buffer, Buffer, Buffer]:
        """Split UPDATE payload into withdrawn, attributes, announced sections.

        Returns memoryview slices for zero-copy access. Converts input to memoryview
        if not already one.
        """
        # Convert to memoryview for zero-copy slicing (memoryview() accepts any Buffer)
        length = len(data)

        # UPDATE minimum: withdrawn_len(2) + attr_len(2) = 4 bytes
        if length < UPDATE_ATTR_LENGTH_HEADER_SIZE:
            # RFC 4271 6.1 lists "the Length field of an UPDATE message is less than the
            # minimum length of the UPDATE message" among the Bad Message Length
            # conditions, so this is a Message Header Error.  3/1 Malformed Attribute List
            # is for what 6.3 describes: a Withdrawn Routes Length or Total Attribute
            # Length which disagrees with a message long enough to hold them, which is the
            # gate below rather than this one
            # RFC 4271 6.1: the Data field carries the erroneous Length field itself
            raise Notify(1, 2, f'UPDATE body of {length} octets', data=pack('!H', Message.HEADER_LEN + length))

        len_withdrawn = unpack('!H', data[0:UPDATE_WITHDRAWN_LENGTH_OFFSET])[0]

        # Verify we have enough data for withdrawn routes + attr length field
        if length < UPDATE_ATTR_LENGTH_HEADER_SIZE + len_withdrawn:
            raise Notify(3, 1, f'UPDATE withdrawn length {len_withdrawn} exceeds available data')

        withdrawn = data[UPDATE_WITHDRAWN_LENGTH_OFFSET : len_withdrawn + UPDATE_WITHDRAWN_LENGTH_OFFSET]

        start_attributes = len_withdrawn + UPDATE_ATTR_LENGTH_HEADER_SIZE
        len_attributes = unpack('!H', data[len_withdrawn + UPDATE_WITHDRAWN_LENGTH_OFFSET : start_attributes])[0]

        # Verify we have enough data for attributes
        if length < start_attributes + len_attributes:
            raise Notify(3, 1, f'UPDATE attributes length {len_attributes} exceeds available data')

        start_announced = len_withdrawn + len_attributes + UPDATE_ATTR_LENGTH_HEADER_SIZE
        attributes = data[start_attributes:start_announced]
        announced = data[start_announced:]

        if (
            UPDATE_WITHDRAWN_LENGTH_OFFSET
            + len_withdrawn
            + UPDATE_WITHDRAWN_LENGTH_OFFSET
            + len_attributes
            + len(announced)
            != length
        ):
            raise Notify(3, 1, 'error in BGP message length, not enough data for the size announced')

        return withdrawn, attributes, announced

    def _classify_announces(
        self, negotiated: Negotiated
    ) -> tuple[list[NLRI], dict[FamilyTuple, list[RoutedNLRI]], bool]:
        """The announcements this session may send: IPv4 unicast, then the rest by MP family.

        The IPv4 ones are bare NLRI, their next hop goes in NEXT_HOP.  The MP ones keep their
        RoutedNLRI, because MP_REACH_NLRI carries the next hop.  The flag says an Empty NLRI
        was seen, which is how an attributes-only UPDATE is asked for.
        """
        # Import here to avoid circular import
        from exabgp.bgp.message.update.nlri.empty import Empty

        v4_announces: list[NLRI] = []
        mp_announces: dict[FamilyTuple, list[RoutedNLRI]] = {}
        has_empty_nlri = False

        # Sort by nlri for deterministic ordering
        for routed in sorted(self._announces, key=lambda r: r.nlri):
            nlri = routed.nlri
            nexthop = routed.nexthop

            # Skip Empty NLRI but remember we had one
            if isinstance(nlri, Empty):
                has_empty_nlri = True
                continue

            if nlri.family().afi_safi() not in negotiated.families:
                continue
            if not self.attributes.otc_allowed(negotiated, nlri.family().afi_safi()):
                continue

            # Wire format validation for announces (not needed for withdraws)
            # Uses shared validation logic - also called at API level for early feedback
            error = validate_announce_nlri(nlri, nexthop)
            if error:
                raise ValueError(error)

            is_v4 = nlri.afi == AFI.ipv4
            is_v4 = is_v4 and nlri.safi == SAFI.unicast
            is_v4 = is_v4 and nexthop.afi == AFI.ipv4

            if is_v4:
                v4_announces.append(nlri)
                continue

            if nexthop.afi != AFI.undefined:
                mp_announces.setdefault(nlri.family().afi_safi(), []).append(routed)
                continue

            if nlri.safi in (SAFI.flow_ip, SAFI.flow_vpn):
                mp_announces.setdefault(nlri.family().afi_safi(), []).append(routed)
                continue

            raise ValueError('unexpected nlri definition ({})'.format(nlri))

        return v4_announces, mp_announces, has_empty_nlri

    def _classify_withdraws(self, negotiated: Negotiated) -> tuple[list[NLRI], dict[FamilyTuple, list[NLRI]], bool]:
        """The withdrawals this session may send: IPv4 unicast, then the rest by MP family.

        Both are bare NLRI, since a withdrawal carries no next hop.  The flag says an Empty
        NLRI was seen, as for the announcements.
        """
        # Import here to avoid circular import
        from exabgp.bgp.message.update.nlri.empty import Empty

        v4_withdraws: list[NLRI] = []
        mp_withdraws: dict[FamilyTuple, list[NLRI]] = {}
        has_empty_nlri = False

        for nlri in sorted(self._withdraws):
            # Skip Empty NLRI in withdraws
            if isinstance(nlri, Empty):
                has_empty_nlri = True
                continue

            if nlri.family().afi_safi() not in negotiated.families:
                continue

            is_v4 = nlri.afi == AFI.ipv4
            is_v4 = is_v4 and nlri.safi == SAFI.unicast

            if is_v4:
                v4_withdraws.append(nlri)
                continue

            # MP withdraws
            mp_withdraws.setdefault(nlri.family().afi_safi(), []).append(nlri)

        return v4_withdraws, mp_withdraws, has_empty_nlri

    def _attribute_sets(
        self, negotiated: Negotiated, only_withdraws: bool, mp_withdraws: dict[FamilyTuple, list[NLRI]]
    ) -> tuple[bytes, bytes, bytes]:
        """The packed attributes the passes send: the IPv4 set, the MP set, and the OTC to add.

        The MP set leaves NEXT_HOP out.  Both are empty when all there is to send is unicast
        or multicast MP withdrawals, and the OTC is empty unless RFC 9234 egress marking adds
        one.
        """
        # If all we have is MP_UNREACH_NLRI, we send no path attribute at all.
        # See RFC4760 that states the following:
        #
        #   An UPDATE message that contains the MP_UNREACH_NLRI is not required
        #   to carry any other path attributes.
        #
        # This used to ask pack_attribute for the attributes without the defaults, and got
        # nothing only because of a precedence bug in it: `set(keys + list(default) if
        # with_default else [])` made the whole concatenation the true branch, so
        # with_default=False encoded nothing whatever the collection held. Now that the
        # brackets are right, what this pass wants has to be said: no attribute field.
        # Asking for the withdrawn route's own attributes instead would put them on the wire
        # and size the withdrawal against them, which is how a withdrawal came to be dropped
        # for the weight of an announcement it was not carrying.
        carries_attributes = True

        if mp_withdraws and only_withdraws:
            # Check if all MP withdraws are unicast/multicast (simple case)
            for family in mp_withdraws.keys():
                afi, safi = family
                if safi not in (SAFI.unicast, SAFI.multicast):
                    break
            # no break - all families are unicast/multicast
            else:
                carries_attributes = False

        base_attr = self.attributes.pack_attribute(negotiated) if carries_attributes else b''
        # RFC 4760 3: "An UPDATE message that carries no NLRI, other than the one encoded in
        # the MP_REACH_NLRI attribute, SHOULD NOT carry the NEXT_HOP attribute."  The classic
        # NLRI and the MP families never share a message below, so the MP messages get their
        # own packing without it.  Sending it was seven octets saying again what MP_REACH
        # already said, and a second place for a peer to read a next hop from.
        mp_attr = self.attributes.pack_attribute(negotiated, without_next_hop=True) if carries_attributes else b''
        otc = b''
        # RFC 9234 5: "The operator MUST NOT have the ability to modify the procedures
        # defined in this section."  This used to also test negotiated.role_otc and the
        # INTERNAL_OTC_NONE marker, which were the two ways an operator could switch the
        # egress marking off.  Both were removed in 6.0.0, so neither can be false; the
        # terms are gone rather than left as conditions nothing can fail.
        if (
            not only_withdraws
            and negotiated.role in (RoleValue.PROVIDER, RoleValue.RS, RoleValue.PEER)
            and Attribute.CODE.OTC not in self.attributes
        ):
            otc = OTC.make_otc(negotiated.local_as).pack_attribute(negotiated)
        return base_attr, mp_attr, otc

    def _v4_withdraw_messages(self, negotiated: Negotiated, nlris: list[NLRI]) -> Generator[bytes, None, bool]:
        """The IPv4 unicast withdrawals, in the Withdrawn Routes field, as few UPDATEs as fit.

        Returns False when one withdrawal is wider than a whole UPDATE, which ends messages()
        as it always has.
        """
        # A withdraw-only UPDATE carries no path attribute, so it has the full budget.
        withdraw_size = negotiated.msg_size - 19 - 2 - 2
        withdraws = b''
        withdraws_size = 0
        for nlri in nlris:
            packed = bytes(nlri.pack_nlri(negotiated))
            if withdraws_size + len(packed) > withdraw_size:
                if not withdraws:
                    # A single withdrawal wider than a whole UPDATE. The reason is not the
                    # attributes: this pass sends none, and the budget is the whole message.
                    log.critical(lazymsg('update.pack.error reason=withdrawal_too_large'), 'parser')
                    return False
                yield Message.frame(
                    Message.CODE.UPDATE, UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(b'')
                )
                withdraws = b''
                withdraws_size = 0
            withdraws += packed
            withdraws_size += len(packed)
        if withdraws:
            yield Message.frame(Message.CODE.UPDATE, UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(b''))
        return True

    def _v4_announce_messages(
        self, negotiated: Negotiated, nlris: list[NLRI], attr: bytes
    ) -> Generator[bytes, None, bool]:
        """The IPv4 unicast announcements, in the NLRI field, as few UPDATEs as fit.

        Returns False when one NLRI does not fit beside the attributes, which ends messages()
        as it always has.
        """
        # What is left of an UPDATE once the path attributes of an ANNOUNCEMENT are in it.
        # 2 bytes for each of the two prefix() header.
        #
        # This budget belongs to the announcement passes and to nothing else.  RFC 4271 4.3
        # makes the Path Attributes field optional, and RFC 4760 3 says an UPDATE carrying
        # MP_UNREACH_NLRI "is not required to carry any other path attributes", so a withdrawal
        # never needs what an announcement needs.  Since the carriers were split it does not
        # even carry it: the passes below send a withdrawal with an empty attribute field.
        #
        # It used to decide both.  Two guards in messages() returned from the whole method
        # when this number reached zero, so attributes close to the negotiated message size threw the
        # pending withdrawals away with the announcement they could not pack.  A withdrawal
        # which is never sent leaves the peer forwarding to a prefix we have stopped
        # advertising and says so nowhere, which is worse than an announcement it never had.
        # The refusal now stands in front of each announcement pass, and the withdrawals are
        # judged on their own budget.
        msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr)

        if nlris and msg_size <= 0:
            # The attributes these routes need leave no room for a single NLRI, so they cannot
            # be announced at all. This is the refusal the two guards in messages() used to
            # make, now made where it applies: the withdrawals have already gone out.
            log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
            return True

        announced = b''
        announced_size = 0
        for nlri in nlris:
            packed = bytes(nlri.pack_nlri(negotiated))
            if announced_size + len(packed) > msg_size:
                if not announced:
                    log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
                    return False
                yield Message.frame(
                    Message.CODE.UPDATE, UpdateCollection.prefix(b'') + UpdateCollection.prefix(attr) + announced
                )
                announced = b''
                announced_size = 0
            announced += packed
            announced_size += len(packed)
        if announced:
            # Native NLRI has been emitted; it must not be repeated in an MP family's packet.
            yield Message.frame(
                Message.CODE.UPDATE, UpdateCollection.prefix(b'') + UpdateCollection.prefix(attr) + announced
            )
        return True

    def _mp_family_messages(
        self,
        negotiated: Negotiated,
        family: FamilyTuple,
        announce_routed: list[RoutedNLRI],
        withdraw_nlris: list[NLRI],
        mp_attr: bytes,
        otc: bytes,
        include_withdraw: bool,
    ) -> Generator[bytes, None, None]:
        """One MP family: its MP_UNREACH_NLRI UPDATEs, then its MP_REACH_NLRI ones."""
        afi, safi = family

        # Use MPNLRICollection for reach/unreach attribute generation
        attr = (
            in_type_order(mp_attr + otc)
            if announce_routed and family in ((AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast))
            else mp_attr
        )
        mp_announce = MPNLRICollection.from_routed(announce_routed, self._attributes, afi, safi)
        mp_withdraw = MPNLRICollection(withdraw_nlris, {}, afi, safi)

        # RFC 7606 5.1 again: an MP_UNREACH_NLRI never shares a message with an
        # MP_REACH_NLRI.  Emitting all the withdrawals first keeps the ordering the
        # shared message used to give, so a prefix is still withdrawn before it is
        # re-announced, including across packet boundaries.
        #
        # The withdrawals are sized on mp_attr, which is what their messages carry, and
        # the announcements on attr, which may hold an OTC the withdrawals do not.  The two
        # are therefore judged separately, for the same reason as the IPv4 passes.
        withdraw_size = negotiated.msg_size - 19 - 2 - 2 - len(mp_attr)
        if include_withdraw and withdraw_nlris:
            if withdraw_size <= 0:
                # A budget which cannot hold an attribute header is one fact about the
                # attributes, not one per route, so it is said here rather than by
                # packed_unreach_attributes once per NLRI.  This used to claim that
                # generator "raises RuntimeError rather than yield nothing, so it is never
                # called with a budget which cannot hold anything": false twice over, since
                # a positive budget narrower than one NLRI walked past this guard and the
                # RuntimeError was an escape into the reactor rather than a refusal.
                log.critical(
                    lazymsg('update.pack.error reason=attributes_too_large afi={afi} safi={safi}', afi=afi, safi=safi),
                    'parser',
                )
            else:
                for mpurnlri in mp_withdraw.packed_unreach_attributes(negotiated, withdraw_size):
                    yield Message.frame(
                        Message.CODE.UPDATE,
                        UpdateCollection.prefix(b'') + UpdateCollection.prefix(mpurnlri + mp_attr),
                    )

        msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr)
        if msg_size <= 0:
            # Only this family's announcements are impossible.  messages() goes on to the
            # families after it, whose attributes may well fit: attr differs between them by
            # the OTC.  Nothing is logged when there was nothing to announce.
            if announce_routed:
                log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
            return

        # RFC 7606 5.1: "The MP_REACH_NLRI or MP_UNREACH_NLRI attribute (if present)
        # SHALL be encoded as the very first path attribute in an UPDATE message", so
        # the attribute goes in front of ORIGIN, AS_PATH and the rest rather than after.
        for mprnlri in mp_announce.packed_reach_attributes(negotiated, msg_size):
            yield Message.frame(
                Message.CODE.UPDATE, UpdateCollection.prefix(b'') + UpdateCollection.prefix(mprnlri + attr)
            )

    # The routes MUST have the same attributes ...
    #
    # Two things about this method which are not visible from inside it.
    #
    # The RFC 7606 5.1 split below, which keeps an announcement and a withdrawal of the same
    # family out of one UPDATE, is correct and is currently UNREACHABLE from the daemon.  No
    # production caller ever builds an UpdateCollection holding both: rib/outgoing.py yields
    # `UpdateCollection([], [nlri], attributes)` for a withdrawal and
    # `UpdateCollection(announces, [], attributes)` for an announcement, never one object with
    # both, and the only collections which do hold both come out of _parse_payload on the
    # receiving side and are never packed again.  So the unit tests in
    # tests/unit/test_update_carrier_split.py are the ONLY exercise the split gets, which is
    # also why re-recording all 395 wire captures for it moved no message count anywhere.
    # Do not read that as dead code to delete: messages() is the public contract for turning a
    # semantic collection into wire format, the RFC forbids the shape whatever builds it, and
    # the day a caller does batch the two sides this is what keeps it legal.
    #
    # And rib/outgoing.py yields one UpdateCollection PER WITHDRAWN NLRI, so two hundred
    # withdrawals leave as two hundred UPDATEs no matter how well this method batches.  That is
    # a real inefficiency, it is why no recorded capture has ever held a batched withdrawal,
    # and it is not fixed here because it belongs to the RIB and needs its own testing.
    def messages(self, negotiated: Negotiated, include_withdraw: bool = True) -> Generator[bytes, None, None]:
        # Sort and classify NLRIs into IPv4 and MP categories
        # v4_announces/v4_withdraws store bare NLRIs (nexthop is in NEXT_HOP attribute for IPv4)
        # mp_announces stores RoutedNLRI by family (nexthop needed for MP_REACH_NLRI encoding)
        # mp_withdraws stores bare NLRI by family (MP_UNREACH_NLRI has no nexthop)
        v4_announces, mp_announces, announced_empty = self._classify_announces(negotiated)
        v4_withdraws, mp_withdraws, withdrew_empty = self._classify_withdraws(negotiated)
        has_empty_nlri = announced_empty or withdrew_empty

        # Check if we have anything to send
        has_v4 = v4_announces or v4_withdraws
        has_mp = mp_announces or mp_withdraws
        if not has_v4 and not has_mp:
            # Attributes-only UPDATE (Empty NLRI case)
            if has_empty_nlri and self._attributes:
                attr = self.attributes.pack_attribute(negotiated, with_default=True)
                # Generate UPDATE with no withdrawn routes and no NLRI, just attributes
                yield Message.frame(Message.CODE.UPDATE, UpdateCollection.prefix(b'') + UpdateCollection.prefix(attr))
            return

        # Check if we only have withdraws (v4 or mp)
        only_withdraws = not v4_announces and not mp_announces
        base_attr, mp_attr, otc = self._attribute_sets(negotiated, only_withdraws, mp_withdraws)
        attr = in_type_order(base_attr + otc) if v4_announces else base_attr

        # RFC 7606 5.1: "An UPDATE message MUST NOT contain more than one of the following:
        # non-empty Withdrawn Routes field, non-empty Network Layer Reachability Information
        # field, MP_REACH_NLRI attribute, and MP_UNREACH_NLRI attribute."  So the two IPv4
        # unicast fields are filled by two separate passes which never share a message.  The
        # withdrawals go first, because a prefix which is in both sets has to be withdrawn
        # before it is re-announced, which is the order a single message used to give for
        # free.  Each pass still fills its field to the negotiated message size, so a table
        # load stays at one message per few hundred prefixes.
        # Sizes are tracked progressively to avoid an O(n) len() on every concatenation.
        # See lab/benchmark_update_size.py for the benchmark (1.3-1.5x speedup).
        if include_withdraw and v4_withdraws:
            if not (yield from self._v4_withdraw_messages(negotiated, v4_withdraws)):
                return

        if not (yield from self._v4_announce_messages(negotiated, v4_announces, attr)):
            return

        # Get all families that have MP announces or withdraws
        all_mp_families = set(mp_announces.keys()) | set(mp_withdraws.keys())

        for family in all_mp_families:
            yield from self._mp_family_messages(
                negotiated,
                family,
                mp_announces.get(family, []),
                mp_withdraws.get(family, []),
                mp_attr,
                otc,
                include_withdraw,
            )

    def pack_messages(self, negotiated: Negotiated, include_withdraw: bool = True) -> Generator['Update', None, None]:
        """Pack this UpdateCollection into wire-format Update messages.

        One UpdateCollection can produce multiple Update messages due to BGP
        message size limits.

        Args:
            negotiated: BGP session negotiated parameters.
            include_withdraw: Whether to include withdrawals in output.

        Yields:
            Update objects containing serialized UPDATE payloads.
        """
        # Import here to avoid circular import
        from exabgp.bgp.message.update import Update

        for msg_bytes in self.messages(negotiated, include_withdraw):
            # BGP message format: marker(16) + length(2) + type(1) + payload
            # Extract payload by removing 19-byte header
            payload = msg_bytes[Message.HEADER_LEN :]
            yield Update(payload)

    # Note: This method can raise ValueError, IndexError, TypeError, struct.error (from unpack).
    # These exceptions are caught by the caller in reactor/protocol.py:read_message() which
    # wraps them in a Notify(1, 0) to signal a malformed message to the peer.
    @staticmethod
    def _withdrawn_in_context(attributes: AttributeCollection, legacy: bool, negotiated: Negotiated) -> str | None:
        """Why the announced routes of this UPDATE are to be treated as withdrawn, None to keep them."""
        # RFC 7606: an UPDATE carrying reachable NLRI must include the attributes
        # needed to interpret those routes. NEXT_HOP applies to the legacy IPv4
        # NLRI field; MP_REACH_NLRI carries its own next hop.
        mandatory = [Attribute.CODE.ORIGIN, Attribute.CODE.AS_PATH] + ([Attribute.CODE.NEXT_HOP] if legacy else [])
        for code in mandatory:
            if code not in attributes:
                return f'the well-known mandatory attribute {Attribute.CODE.name(code)} is missing'
        path = attributes.get(Attribute.CODE.AS_PATH, None)
        reason = UpdateCollection._malformed_confederation_path(path, negotiated)
        if reason is None:
            reason = UpdateCollection._not_first_as_of_peer(path, negotiated)
        if reason is not None:
            return reason
        # RFC 9774 3: a route with an AS_SET or AS_CONFED_SET is treated as withdrawn,
        # unless the operator configured the neighbour to accept them (`as-set accept`).
        # An AS4_PATH still here was not dropped by RFC 6793 and its sets now count.
        neighbor = getattr(negotiated, 'neighbor', None)
        if getattr(neighbor, 'as_set', 'withdraw') == 'accept':
            return None
        for code in (Attribute.CODE.AS_PATH, Attribute.CODE.AS4_PATH):
            path = attributes.get(code, None)
            if isinstance(path, ASPath) and path.has_set():
                return f'an AS_SET or AS_CONFED_SET in the {Attribute.CODE.name(code)} (RFC 9774)'
        return None

    @staticmethod
    def _withdraw_malformed_routes(mp_reach: list[RoutedNLRI], withdraws: list[NLRI]) -> list[RoutedNLRI]:
        """The routes of MP_REACH_NLRI still announced, once the malformed ones are withdrawn.

        A route whose decoder kept its key but found the rest malformed (see
        NLRI.withdrawn_on_receipt) is treat-as-withdraw on its own, the rest of the UPDATE
        standing: it joins `withdraws`, which is changed in place.
        """
        announced: list[RoutedNLRI] = []
        for routed in mp_reach:
            reason = routed.nlri.withdrawn_on_receipt()
            if reason is None:
                announced.append(routed)
                continue
            log.warning(
                lazymsg('update.treat-as-withdraw nlri={nlri} reason="{reason}"', nlri=routed.nlri, reason=reason),
                'parser',
            )
            withdraws.append(routed.nlri)
        return announced

    @staticmethod
    def _withdrawn_for_its_routes(
        mp_reach: list[RoutedNLRI], attributes: AttributeCollection, negotiated: Negotiated
    ) -> str | None:
        """Why a route of MP_REACH_NLRI makes this UPDATE treat-as-withdraw, None if none does.

        Decided once the NLRI are built, as the rules need both the routes and the
        attributes, and the action is on the UPDATE: RFC 7606 withdraws all its routes.
        """
        for routed in mp_reach:
            reason = _withdraw_reason(routed.nlri, attributes, negotiated)
            if reason is not None:
                return f'{routed.nlri}: {reason}'
        return None

    @staticmethod
    def _malformed_confederation_path(path: Attribute | None, negotiated: Negotiated) -> str | None:
        """RFC 5065 5: the two AS_PATHs a speaker must call malformed, None for any other.

        RFC 7606 turns the malformed AS_PATH RFC 4271 6.3 would reset the session for into
        a withdraw.
        """
        if not isinstance(path, ASPath):
            return None
        # Confederation segments from a neighbour not in our confederation. With none
        # configured, no external neighbour is in the same one as us; an internal one is
        # in our own AS, and is left alone.
        outside = negotiated.confed_outside if negotiated.confederation else not negotiated.is_internal_neighbor
        if outside:
            return 'confederation segments from outside the confederation (RFC 5065 5)' if path.has_confed() else None
        # from another Member-AS, a path which does not start with an AS_CONFED_SEQUENCE
        if negotiated.confed_member:
            segments = path.aspath
            if not segments or not isinstance(segments[0], CONFED_SEQUENCE):
                return 'a path from another Member-AS not starting with an AS_CONFED_SEQUENCE (RFC 5065 5)'
        return None

    @staticmethod
    def _not_first_as_of_peer(path: Attribute | None, negotiated: Negotiated) -> str | None:
        """RFC 8955 6 and RFC 4271 6.3: an EBGP route's AS_PATH starts with the neighbour's AS.

        RFC 4271 makes the check optional, RFC 8955 makes it a MUST. A route server does
        not prepend its own AS, so `enforce-first-as false` on its neighbour turns it off.
        A neighbouring Member-AS is checked by the RFC 5065 rule above instead. RFC 7606
        turns the malformed AS_PATH of RFC 4271 6.3 into a withdraw.
        """
        if not isinstance(path, ASPath) or negotiated.is_internal_neighbor:
            return None
        neighbor = getattr(negotiated, 'neighbor', None)
        if neighbor is None or not neighbor.enforce_first_as:
            return None
        segments = path.aspath
        if segments and isinstance(segments[0], SEQUENCE) and segments[0] and segments[0][0] == negotiated.peer_as:
            return None
        return f'the AS_PATH does not start with the peer AS {negotiated.peer_as}'

    @classmethod
    def _parse_payload(cls, data: Buffer, negotiated: Negotiated) -> UpdateCollection:
        """Parse a raw UPDATE payload (after the BGP header) for Update.parse().

        Decoded with a `negotiated.outbound()`, it is an UPDATE we sent, read as written.
        """
        withdrawn_view, attr_view, announced_view = cls.split(data)

        if not withdrawn_view:
            log.debug(lazymsg('update.withdrawn status=none'), 'routes')

        # Convert memoryview slices to bytes for downstream parsing
        # (NLRI.unpack_nlri and AttributeCollection.unpack still use bytes)
        withdrawn_bytes: Buffer = bytes(withdrawn_view)
        announced_bytes: Buffer = bytes(announced_view)
        attributes = AttributeCollection.unpack(bytes(attr_view), negotiated)

        if not announced_view:
            log.debug(lazymsg('update.announced status=none'), 'routes')

        # Is the peer going to send us some Path Information with the route (AddPath)
        addpath = negotiated.required(AFI.ipv4, SAFI.unicast)

        # empty string for IP.NoNextHop, the packed IP otherwise (without the 3/4 bytes of attributes headers)
        nexthop = attributes.get(Attribute.CODE.NEXT_HOP, IP.NoNextHop)
        if negotiated.from_peer:
            cls._warn_next_hop_is_ours(nexthop, negotiated)

        withdraws = cls._unpack_withdrawn(withdrawn_bytes, addpath, negotiated)
        legacy = cls._unpack_announced(announced_bytes, cls._routed_next_hop(nexthop), addpath, negotiated)

        unreach = attributes.pop(MPURNLRI.ID, None)
        reach = attributes.pop(MPRNLRI.ID, None)

        if unreach is not None and isinstance(unreach, MPURNLRI):
            # MPURNLRI implements __iter__ yielding NLRI
            withdraws.extend(unreach)

        # MP_REACH_NLRI carries its own next hop; iter_routed() preserves it while
        # converting each contained NLRI to the semantic routed form.
        mp_reach = list(reach.iter_routed()) if isinstance(reach, MPRNLRI) else []
        mp_reach = cls._withdraw_malformed_routes(mp_reach, withdraws)

        # An UPDATE we sent is told to the API as it went out: the checks below are the
        # ones a receiver makes on its peer's routes, and on our own they withdrew an EBGP
        # route for not starting with the peer's AS, or one with an AS_SET (RFC 9774).
        if not negotiated.from_peer:
            return cls(legacy + mp_reach, withdraws, attributes)

        attributes = cls._with_next_hop_decided(attributes, bool(announced_view), isinstance(reach, MPRNLRI))
        # RFC 7606 5.2 is decided on what the UPDATE encodes, before any route is dropped
        # below for what it means rather than for how it was written.
        has_reachable_nlri = bool(announced_view) or isinstance(reach, MPRNLRI)
        cls._reset_without_reachable_nlri(attributes, has_reachable_nlri)

        context = None
        if legacy or mp_reach:
            context = cls._withdrawn_in_context(attributes, bool(announced_view), negotiated)
            if context is None:
                context = cls._withdrawn_for_its_routes(mp_reach, attributes, negotiated)
        if context is not None:
            # AttributeCollection.unpack() may have returned the session's cached
            # collection. These reasons are UPDATE context, not an interpretation of
            # the attribute bytes, so adding the marker to that shared object would
            # poison later updates with the same bytes. Copy the mapping only here.
            attributes = attributes.copy()
            attributes.add(TreatAsWithdraw())

        collection = cls._routes(legacy, mp_reach, withdraws, attributes)
        cls._log_malformed(data, negotiated, collection, attributes.malformed, context)
        return collection

    @staticmethod
    def _with_next_hop_decided(attributes: AttributeCollection, legacy: bool, mp_reach: bool) -> AttributeCollection:
        """What a malformed NEXT_HOP does to this UPDATE, now the UPDATE is known.

        RFC 7606 7.3 makes it treat-as-withdraw. RFC 4760 3 has the NEXT_HOP of an UPDATE
        whose only NLRI are in MP_REACH_NLRI ignored, so there it withdraws nothing: those
        routes carry their own next hop. It used to withdraw them all.
        """
        reason = attributes.next_hop_malformed
        if not reason:
            return attributes
        # the collection may be the session's cached one, so the change is made on a copy
        decided = attributes.copy()
        if mp_reach and not legacy:
            decided.malformed.append((Attribute.CODE.NEXT_HOP, NEXT_HOP_IGNORED_ACTION, reason))
            return decided
        decided.malformed.append((Attribute.CODE.NEXT_HOP, TREAT_AS_WITHDRAW_ACTION, reason))
        decided.add(TreatAsWithdraw(Attribute.CODE.NEXT_HOP))
        return decided

    @staticmethod
    def _log_malformed(
        payload: Buffer,
        negotiated: Negotiated,
        collection: UpdateCollection,
        malformed: list[tuple[int, str, str]],
        context: str | None,
    ) -> None:
        """RFC 7606 6: one error per malformed UPDATE, naming its NLRI and holding its bytes.

        Treat-as-withdraw and attribute discard change the routes with no NOTIFICATION, so
        this line is the only record of why. Both lists the peer sizes are capped.
        """
        reasons = [f'{Attribute.CODE.name(code)} {action}: {reason}' for code, action, reason in malformed]
        if context is not None:
            reasons.append(f'{TREAT_AS_WITHDRAW_ACTION}: {context}')
        if not reasons:
            return
        everything = chain((routed.nlri for routed in collection.announces), collection.withdraws)
        nlri = [str(nlri) for nlri in islice(everything, MAX_LOGGED_NLRI + 1)]
        if len(nlri) > MAX_LOGGED_NLRI:
            nlri[MAX_LOGGED_NLRI:] = [
                f'and {len(collection.announces) + len(collection.withdraws) - MAX_LOGGED_NLRI} more'
            ]
        message = Message.frame(Message.CODE.UPDATE, payload)
        shown = message[:MAX_LOGGED_UPDATE_OCTETS].hex()
        if len(message) > MAX_LOGGED_UPDATE_OCTETS:
            shown += f'... ({len(message)} octets)'
        log.error(
            lazymsg(
                'update.malformed peer={peer} reason="{reason}" nlri=[{nlri}] update={update}',
                peer=negotiated.peer_address,
                reason='; '.join(reasons),
                nlri=', '.join(nlri),
                update=shown,
            ),
            'parser',
        )

    @classmethod
    def _routes(
        cls,
        legacy: list[RoutedNLRI],
        mp_reach: list[RoutedNLRI],
        withdraws: list[NLRI],
        attributes: AttributeCollection,
    ) -> UpdateCollection:
        """The collection an UPDATE decodes to, once its routes and attributes are known."""
        # Treat-as-withdraw is an action on every announced route, not merely a
        # diagnostic attribute. NLRI parsing has completed at this point, so all
        # affected legacy and MP_REACH routes can be moved safely. It comes before the
        # RFC 4271 6.3 filter: a MUST to withdraw outranks a SHOULD to ignore.
        if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in attributes:
            withdraws.extend(routed.nlri for routed in legacy + mp_reach)
            return cls([], withdraws, attributes)

        announces = [routed for routed in legacy if cls._semantically_correct(routed)] + mp_reach
        valid = cls._without_invalid_prefix_sid(attributes, announces)
        return cls(announces, cls._not_announced(withdraws, announces), valid)

    @staticmethod
    def _without_invalid_prefix_sid(
        attributes: AttributeCollection, announces: list[RoutedNLRI]
    ) -> AttributeCollection:
        """RFC 8669 3.1 and 4.1: on labelled unicast, a Prefix-SID with no Label-Index is invalid.

        Invalid means ignored and not propagated (section 6), so the attribute is discarded
        and the routes kept. Only labelled unicast: the Label-Index is ignored on other
        families, and RFC 9252 puts SRv6 service TLVs with no Label-Index in this same
        attribute on VPN and EVPN routes. Decided here, after the NLRI are built, because
        the family is in MP_REACH_NLRI, a sibling of the attribute.
        """
        if Attribute.CODE.BGP_PREFIX_SID not in attributes:
            return attributes
        if not any(routed.nlri.safi == SAFI.nlri_mpls for routed in announces):
            return attributes
        # the attribute stored under BGP_PREFIX_SID is the Prefix-SID attribute
        prefix_sid = cast(PrefixSid, attributes[Attribute.CODE.BGP_PREFIX_SID])
        if any(tlv.TLV == SrLabelIndex.TLV for tlv in prefix_sid.sr_attrs):
            return attributes
        log.warning(lazymsg('update.prefix-sid.invalid reason=no-label-index action=discard'), 'parser')
        # the collection may be the session's cached one, so the change is made on a copy
        discarded = attributes.copy()
        discarded.remove(Attribute.CODE.BGP_PREFIX_SID)
        discarded.add(Discard(Attribute.CODE.BGP_PREFIX_SID))
        return discarded

    @staticmethod
    def _warn_next_hop_is_ours(nexthop: Attribute | IP, negotiated: Negotiated) -> None:
        """RFC 4271 5.1.3: NEXT_HOP MUST NOT be the IP address of the receiving speaker.

        Logged rather than acted on: the peer may simply have a misconfigured next hop.
        """
        neighbor = getattr(negotiated, 'neighbor', None)
        if nexthop is IP.NoNextHop or neighbor is None:
            return
        try:
            local_address = neighbor.session.local_address
            nexthop_packed = getattr(nexthop, '_packed', b'')
            local_packed = getattr(local_address, '_packed', b'')
            if local_address is not None and nexthop_packed and local_packed and nexthop_packed == local_packed:
                log.warning(
                    lambda: 'received NEXT_HOP {} equals our local address (RFC 4271 violation)'.format(nexthop),
                    'parser',
                )
        except (TypeError, KeyError) as exc:
            # Every access above is already guarded, so reaching here means the
            # neighbour is not shaped the way this check assumes. That is worth knowing
            # about rather than passing over: the comment which used to be here said
            # "may be a mock", which is a reason from the tests and not from production.
            log.debug(lazymsg('update.nexthop.check.skipped error={error}', error=str(exc)), 'parser')

    @staticmethod
    def _routed_next_hop(nexthop: Attribute | IP) -> IP:
        """The NEXT_HOP attribute as the IP a RoutedNLRI of the legacy NLRI field carries."""
        if isinstance(nexthop, IP):
            return nexthop
        if isinstance(nexthop, NextHop):
            packed = nexthop._packed
            if len(packed) == IPv4.BYTES:
                return IPv4(packed)
            if len(packed) == IPv6.BYTES:
                return IPv6(packed)
            # the else used to be IPv6(packed) for every other length, and NextHop.UNSET
            # carries no address at all, so its empty bytes went to inet_ntop and came
            # back as a ValueError from here: past the decoders, in the semantic
            # transformation, where the TREAT_AS_WITHDRAW flag on NextHop can no longer
            # catch anything
        return IP.NoNextHop

    @staticmethod
    def _unpack_withdrawn(field: Buffer, addpath: bool, negotiated: Negotiated) -> list[NLRI]:
        """The prefixes of the WITHDRAWN ROUTES field.

        Bounded by the field: NLRI.unpack_nlri consumes at least the mask octet of every
        prefix, or raises.
        """
        withdraws: list[NLRI] = []
        while field:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, field, Action.WITHDRAW, addpath, negotiated)
            assert len(left) < len(field), 'an NLRI decoder returned without consuming its input'
            log.debug(lazymsg('withdrawn NLRI {nlri}', nlri=nlri), 'routes')
            field = left
            if nlri is not NLRI.INVALID:
                withdraws.append(nlri)
        return withdraws

    @staticmethod
    def _unpack_announced(field: Buffer, nexthop: IP, addpath: bool, negotiated: Negotiated) -> list[RoutedNLRI]:
        """The prefixes of the NLRI field, each with the NEXT_HOP of the UPDATE."""
        announces: list[RoutedNLRI] = []
        while field:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, field, Action.ANNOUNCE, addpath, negotiated)
            assert len(left) < len(field), 'an NLRI decoder returned without consuming its input'
            field = left
            if nlri is not NLRI.INVALID:
                log.debug(lazymsg('announced NLRI {nlri}', nlri=nlri), 'routes')
                announces.append(RoutedNLRI(nlri, nexthop))
        return announces

    @staticmethod
    def _reset_without_reachable_nlri(attributes: AttributeCollection, has_reachable_nlri: bool) -> None:
        """RFC 7606 5.2: a treat-as-withdraw error in an UPDATE with no reachable NLRI resets.

        Such an UPDATE carries attributes other than MP_UNREACH_NLRI (the one in error is
        one), so there is no route to withdraw and no proof that the NLRI field was read
        correctly. Attribute discard is exempt by name, and a Discard marker never gets
        here as a TreatAsWithdraw. 3/1 Malformed Attribute List: the attribute list is
        what could not be trusted.
        """
        if has_reachable_nlri:
            return
        marker = attributes.get(Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW, None)
        if marker is None:
            return
        raise Notify(3, 1, f'{marker} in an UPDATE with no reachable NLRI (RFC 7606 5.2)')

    @staticmethod
    def _semantically_correct(routed: RoutedNLRI) -> bool:
        """RFC 4271 6.3: log and ignore a route with a semantically incorrect value.

        Only the legacy NLRI field and its NEXT_HOP, which is all RFC 4271 describes.
        The route is ignored, not withdrawn, and the UPDATE is otherwise processed.
        """
        reason = _semantic_error(routed)
        if reason is None:
            return True
        log.error(
            lazymsg('update.route.ignored nlri={nlri} reason="{reason}"', nlri=routed.nlri, reason=reason), 'parser'
        )
        return False

    @staticmethod
    def _not_announced(withdraws: list[NLRI], announces: list[RoutedNLRI]) -> list[NLRI]:
        """RFC 4271 4.3: act as though the withdrawals did not hold a prefix also announced.

        Otherwise a consumer which applies withdrawals after announcements, or batches
        them, removes the route the same UPDATE installs.
        """
        if not withdraws or not announces:
            return withdraws
        announced = {routed.nlri.index() for routed in announces}
        return [nlri for nlri in withdraws if nlri.index() not in announced]

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> 'UpdateCollection':
        """Parse raw UPDATE payload bytes into UpdateCollection.

        An End-of-RIB (RFC 4724) is returned marked with its family, see make_eor.
        """
        from exabgp.bgp.message.update.eor import EOR

        eor = EOR.from_body(data)
        if eor is not None:
            return cls.make_eor(eor.afi, eor.safi)

        # Parse normally
        return cls._parse_payload(data, negotiated)
