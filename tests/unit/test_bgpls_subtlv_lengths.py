"""A recognised BGP-LS TLV holds its sub-TLV lengths to what is actually there.

RFC 9552 8.2.2 asks a speaker to check "the length of each TLV and, when the TLV is recognized
then, the length of its sub-TLVs in the BGP-LS Attribute are valid". The walks in the SRv6
End.X TLVs read `data[4 : length + 4]`, a slice, and a slice cannot raise however large the
declared length is, so the peer's length was compared with nothing at all: a sub-TLV claiming a
thousand octets inside a thirty octet TLV came back as whatever happened to be behind it.

There is no traceback for that, which is the difficulty. It was silent acceptance, and silent
acceptance is why random-byte sweeps came back clean over the whole area.

Two cases, answered differently on purpose:

- a sub-TLV **claiming** more octets than remain is refused. The peer got a length wrong about
  data we would go on to read.
- a trailing remnant too short to be a header is ignored. Refusing it discarded the whole
  attribute, so a peer which pads its TLV lost a route; main's `qa/bin/compat_gate` counted
  nine such inputs, TLV 1106 at payload lengths 23, 24 and 25 over a 22 octet fixed part.
  Three stray octets cost no route and tell an operator nothing they can act on.

The member name an unrecognised sub-TLV gets differs between the two TLVs, `subtlv-not-implemented-N`
for End.X and `N-undecoded` for its LAN siblings. Both are published and neither may be renamed,
so the shared helper takes a formatter and the names are pinned here.
"""

from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

ENDX = 1106
LAN_ISIS = 1107

HEAD = pack('!HBBBB', 57, 0x80, 0, 0, 0)  # behavior, flags, algorithm, weight, reserved
SID = bytes.fromhex('fc000000000000000000000000000003')
ISIS_SYSTEM_ID = bytes([0x19, 0x00, 0x95, 0x00, 0x20, 0x02])

ENDX_FIXED = HEAD + SID
LAN_ISIS_FIXED = HEAD + ISIS_SYSTEM_ID + SID

UNKNOWN_SUBTLV = 9999


def render(code, payload):
    return LinkState.unpack(pack('!HH', code, len(payload)) + payload, None, None).json()


@pytest.mark.parametrize('code,fixed', [(ENDX, ENDX_FIXED), (LAN_ISIS, LAN_ISIS_FIXED)])
def test_the_fixed_part_on_its_own_is_accepted(code, fixed):
    """The common case, and the control for everything below."""
    assert '"sid": "fc00::3"' in render(code, fixed)


@pytest.mark.parametrize('code,fixed', [(ENDX, ENDX_FIXED), (LAN_ISIS, LAN_ISIS_FIXED)])
@pytest.mark.parametrize('claimed', [8, 100, 1000, 0xFFFF])
def test_a_sub_tlv_claiming_more_than_is_there_is_refused(code, fixed, claimed):
    """The half worth keeping. Nothing compared the declared length with the buffer."""
    payload = fixed + pack('!HH', UNKNOWN_SUBTLV, claimed) + b'\xaa\xbb'

    with pytest.raises(Notify):
        render(code, payload)


@pytest.mark.parametrize('code,fixed', [(ENDX, ENDX_FIXED), (LAN_ISIS, LAN_ISIS_FIXED)])
@pytest.mark.parametrize('remnant', [1, 2, 3])
def test_a_trailing_remnant_is_ignored_rather_than_refused(code, fixed, remnant):
    """The forgiven half. Refusing cost a route over octets nobody can act on."""
    payload = fixed + bytes([0x30] * remnant)

    assert '"sid": "fc00::3"' in render(code, payload)


@pytest.mark.parametrize('code,fixed', [(ENDX, ENDX_FIXED), (LAN_ISIS, LAN_ISIS_FIXED)])
@pytest.mark.parametrize('remnant', [1, 2, 3])
def test_an_ignored_remnant_invents_no_member(code, fixed, remnant):
    """Forgiving it must not bring back a member built from whatever the octets say."""
    with_remnant = render(code, fixed + bytes([0x30] * remnant))
    without = render(code, fixed)

    assert with_remnant == without


def test_the_endx_unknown_member_name_is_unchanged():
    """`subtlv-not-implemented-N`. A parser in use today reads this key."""
    emitted = render(ENDX, ENDX_FIXED + pack('!HH', UNKNOWN_SUBTLV, 2) + b'\xaa\xbb')

    assert f'"subtlv-not-implemented-{UNKNOWN_SUBTLV}": "0xAABB"' in emitted


def test_the_lan_unknown_member_name_is_unchanged():
    """`N-undecoded`, which differs from End.X's and must keep differing."""
    emitted = render(LAN_ISIS, LAN_ISIS_FIXED + pack('!HH', UNKNOWN_SUBTLV, 2) + b'\xaa\xbb')

    assert f'"{UNKNOWN_SUBTLV}-undecoded": "0xAABB"' in emitted


@pytest.mark.parametrize('code,fixed', [(ENDX, ENDX_FIXED), (LAN_ISIS, LAN_ISIS_FIXED)])
def test_a_sub_tlv_whose_length_agrees_is_still_decoded(code, fixed):
    """The positive half: an honest length is read, and read as a sub-TLV."""
    emitted = render(code, fixed + pack('!HH', UNKNOWN_SUBTLV, 4) + b'\xde\xad\xbe\xef')

    assert '0xDEADBEEF' in emitted
