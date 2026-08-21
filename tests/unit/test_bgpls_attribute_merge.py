#!/usr/bin/env python3
# encoding: utf-8

"""One BGP-LS attribute member per name, and every value it was given

register(lsid=N) mints a separate subclass per lsid, so a class registered under
several of them becomes several classes with several TLV values. LocalTeRid is
registered for 1028 and 1029, the IPv4 and IPv6 spellings of one Local TE Router
ID, so the merge keyed on

    if k.TLV == instance.TLV:

could never pair them. A router announcing both emitted the member twice:

    "local-te-router-ids": ["10.0.202.1"], "local-te-router-ids": ["fc00:1000:112::1"]

which is legal-but-lossy JSON. json.loads keeps the last, so every consumer
silently dropped the IPv4 address, and the recorded decoding fixture had the loss
baked into its expected output. The duplicate is the visible half; the data loss
is the bug.

Deliberately NOT fixed here: remote-te-router-id and sr-adj collide the same way,
but their members are a string and an object, so merging them changes the type a
consumer receives. local-te-router-ids is already a plural list, so merging two
lists into one is the whole fix and changes no type at all. The others are left
alone on this branch on purpose, and the tests below pin that, so that widening
the fix stays a decision rather than an accident.
"""

import json
from struct import pack

from unittest.mock import Mock

import pytest

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS, LinkState
from exabgp.bgp.message.direction import Direction

LOCAL_TE_RID_V4 = 1028
LOCAL_TE_RID_V6 = 1029


def tlv(code, value):
    return pack('!HH', code, len(value)) + value


def unpack_attribute(*tlvs):
    return LinkState.unpack(b''.join(tlvs), Direction.IN, Mock())


def members(attribute):
    """Every key the rendered attribute carries, duplicates included"""
    names = []

    def hook(pairs):
        names.extend(k for k, _ in pairs)
        return dict(pairs)

    json.loads(attribute.json(), object_pairs_hook=hook)
    return names


IPV4 = bytes([10, 0, 202, 1])
IPV6 = bytes([0xFC, 0x00, 0x10, 0x00, 0x01, 0x12]) + b'\x00' * 9 + b'\x01'


class TestAnAliasPairBecomesOneMember:
    def test_the_name_appears_once(self) -> None:
        attribute = unpack_attribute(tlv(LOCAL_TE_RID_V4, IPV4), tlv(LOCAL_TE_RID_V6, IPV6))
        assert members(attribute).count('local-te-router-ids') == 1

    def test_and_carries_both_addresses(self) -> None:
        attribute = unpack_attribute(tlv(LOCAL_TE_RID_V4, IPV4), tlv(LOCAL_TE_RID_V6, IPV6))
        rendered = json.loads(attribute.json())['local-te-router-ids']
        assert '10.0.202.1' in rendered, 'the IPv4 router-id is what a JSON parser used to drop'
        assert len(rendered) == 2

    def test_the_member_is_still_a_list(self) -> None:
        # the reason this pair is safe to merge and the others are not: a list
        # of one becoming a list of two changes nothing for a consumer, where a
        # string becoming a list would
        attribute = unpack_attribute(tlv(LOCAL_TE_RID_V4, IPV4))
        assert isinstance(json.loads(attribute.json())['local-te-router-ids'], list)

    @pytest.mark.parametrize('order', [(LOCAL_TE_RID_V4, LOCAL_TE_RID_V6), (LOCAL_TE_RID_V6, LOCAL_TE_RID_V4)])
    def test_whichever_order_they_arrive_in(self, order) -> None:
        payload = {LOCAL_TE_RID_V4: IPV4, LOCAL_TE_RID_V6: IPV6}
        attribute = unpack_attribute(*[tlv(code, payload[code]) for code in order])
        assert len(json.loads(attribute.json())['local-te-router-ids']) == 2

    def test_one_alone_is_unchanged(self) -> None:
        attribute = unpack_attribute(tlv(LOCAL_TE_RID_V4, IPV4))
        assert json.loads(attribute.json())['local-te-router-ids'] == ['10.0.202.1']


class TestTheGroupingCannotSwallowUnrelatedTlvs:
    """Grouping on the JSON name is only safe where a name was actually chosen

    Srv6EndX, SrAdjacencyLan and both Srv6LanEndX classes set MERGE but never set
    JSON, rendering through their own json() instead. They therefore all share
    BaseLS's unset default, and grouping on it blindly would collapse four
    unrelated TLVs into one member. They group on nothing instead and keep the
    TLV behaviour they had.
    """

    def test_a_class_which_names_its_member_groups_on_that_name(self) -> None:
        klass = LinkState.registered_lsids[LOCAL_TE_RID_V4]
        assert klass([]).merge_key() == 'local-te-router-ids'

    def test_the_two_spellings_agree_on_it(self) -> None:
        v4 = LinkState.registered_lsids[LOCAL_TE_RID_V4]
        v6 = LinkState.registered_lsids[LOCAL_TE_RID_V6]
        assert v4.TLV != v6.TLV, 'distinct subclasses, which is why TLV could not pair them'
        assert v4([]).merge_key() == v6([]).merge_key() is not None

    def test_a_class_which_never_set_one_groups_on_nothing(self) -> None:
        unnamed = [
            k for k in LinkState.registered_lsids.values() if getattr(k, 'MERGE', False) and k.JSON == BaseLS.JSON
        ]
        assert unnamed, 'no MERGE class leaves JSON unset; this guard now protects nothing'
        for klass in unnamed:
            assert klass.__new__(klass).merge_key() is None, klass.__name__

    def test_only_spellings_of_one_tlv_share_a_grouping_key(self) -> None:
        # the alias pair SHARES its key on purpose, so uniqueness is the wrong
        # property. What must hold is that everything sharing a key is the same
        # TLV wearing different lsids, which REPR names
        families = {}
        for klass in LinkState.registered_lsids.values():
            if not getattr(klass, 'MERGE', False):
                continue
            key = klass.__new__(klass).merge_key()
            if key is not None:
                families.setdefault(key, set()).add(klass.REPR)
        assert families, 'nothing groups by name any more'
        for key, reprs in families.items():
            assert len(reprs) == 1, f'{key} would merge unrelated TLVs: {sorted(reprs)}'


class TestWhatThisBranchDeliberatelyLeavesAlone:
    """Pinned so widening the fix is a decision, not a surprise

    remote-te-router-id renders a string and sr-adj renders an object. Merging
    either changes the type a consumer receives, which this branch will not do.
    The collision is real and documented in CHANGELOG; these tests fail the day
    someone changes it, which is the point.
    """

    def test_the_remote_router_id_is_not_grouped(self) -> None:
        klass = LinkState.registered_lsids[1030]
        assert klass.__new__(klass).merge_key() is None

    def test_and_still_renders_a_bare_string(self) -> None:
        attribute = unpack_attribute(tlv(1030, IPV4))
        assert isinstance(json.loads(attribute.json())['remote-te-router-id'], str)


class TestAnUnimplementedCodeDoesNotCollapse:
    """The hazard the guard exists for, arriving through a different door

    get_ls_class mints one class per unknown code with

        type('GenericLSID_%d' % code, GenericLSID.__bases__, dict(GenericLSID.__dict__))

    which makes each one a SIBLING of GenericLSID rather than a subclass, the
    same identity trap as register(lsid=N). Every one of them sets MERGE and
    none of them sets JSON, so they all share BaseLS's unset default. Grouping
    on the name without checking it was ever chosen would collapse every
    unimplemented TLV a peer sends into a single member.

    Found by the session working main, where it had to be solved by setting JSON
    per generic class and by making GENERIC a flag rather than an issubclass
    check, precisely because the sibling relationship defeats issubclass. Here
    merge_key() already answers None for anything still on the default, so the
    generics group on nothing and keep their per-code names.
    """

    def test_two_unknown_codes_stay_apart(self) -> None:
        attribute = unpack_attribute(tlv(1234, b'\xaa\xbb'), tlv(5678, b'\xcc\xdd'))
        rendered = json.loads(attribute.json())
        assert rendered['generic-lsid-1234'] == ['0xAABB']
        assert rendered['generic-lsid-5678'] == ['0xCCDD']

    def test_the_same_unknown_code_twice_still_merges(self) -> None:
        # they may repeat: we cannot claim a TLV we have not implemented is
        # forbidden from repeating, so this half must keep working
        attribute = unpack_attribute(tlv(1234, b'\xaa\xbb'), tlv(1234, b'\xcc\xdd'))
        assert json.loads(attribute.json())['generic-lsid-1234'] == ['0xAABB', '0xCCDD']

    def test_a_generic_groups_on_nothing(self) -> None:
        klass = LinkState.registered_lsids.get(1234) or LinkState.klass(1234)
        instance = klass.__new__(klass)
        assert instance.MERGE is True, 'the same code repeating must still merge'
        assert instance.JSON == BaseLS.JSON, 'and it never chose a name'
        assert instance.merge_key() is None, 'so it must group on nothing'


class TestAKnownDisagreementLeftAlone:
    """IsisArea renders one value as two different types

    content is an int and json() wraps it in quotes, so the JSON API says
    "area-id": "4784129" while as_dict() says 4784129. Two renderers over one
    value, disagreeing.

    NOT fixed here. Either side of it is a compatibility break on a stable
    branch: making json() emit a number changes the type every JSON consumer
    receives, and making as_dict() emit a string changes it for the others. It
    is pinned instead, so that changing it is a decision rather than a side
    effect of some later merge work, which is exactly how it would happen.

    Flagged by the session working main, who hit it while turning area-id into
    an array and would have silently changed a string into a number for every
    consumer.
    """

    @staticmethod
    def isis_area():
        klass = LinkState.registered_lsids[1027]
        return klass.unpack(bytes([0x49, 0x00, 0x01]))

    def test_the_json_api_renders_it_as_a_string(self) -> None:
        assert self.isis_area().json() == '"area-id": "4784129"'

    def test_as_dict_renders_it_as_a_number(self) -> None:
        assert self.isis_area().as_dict() == {'area-id': 4784129}

    def test_and_they_disagree_which_is_the_point(self) -> None:
        area = self.isis_area()
        rendered = json.loads('{%s}' % area.json())['area-id']
        assert isinstance(rendered, str)
        assert isinstance(area.as_dict()['area-id'], int)
