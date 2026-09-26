"""Aggregator.json() raised on every value: the speaker is an address, formatted with %d.

`'{ "asn" : %d, "speaker" : "%d" }' % (self.asn, self.speaker)` fails with TypeError, as the
speaker is an IPv4, not a number; 5.0.13 failed too, with AttributeError. No session reaches it
today, as an UPDATE renders AGGREGATOR through the attribute collection and folds AS4_AGGREGATOR
into it (RFC 6793), but the method is public and qa/bin/compat_gate calls it. main already uses %s.
"""

import json

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.aggregator import Aggregator, Aggregator4
from exabgp.protocol.ip import IPv4


@pytest.mark.parametrize('klass', [Aggregator, Aggregator4])
def test_json_is_valid_and_names_the_speaker(klass) -> None:
    rendered = klass(ASN(65001), IPv4.create('192.0.2.1')).json()
    assert json.loads(rendered) == {'asn': 65001, 'speaker': '192.0.2.1'}
