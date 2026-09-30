#!/usr/bin/env python3
"""The EOR an API process is told about has to be JSON it can parse.

`EOR.NLRI.json()` returned a bare `"eor": {...}` key and value.  Every caller puts
NLRI renderings into a list, `', '.join(nlri.json(...) for nlri in nlris)` between
`[` and `]` in `reactor/api/response/json.py`, so the line a process received for
an end of RIB marker could not be parsed at all.

Nothing in `qa/` recorded that line, which is why it went unnoticed.  The one
script which does read sent updates, `etc/exabgp/run/api-rr-rib.run`, drops it in
`except ValueError: continue` and carries on, so the breakage was silent there too.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.eor import EOR
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.reactor.api.response.json import JSON


def test_eor_nlri_json_is_an_object():
    nlri = EOR.NLRI(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)

    rendered = json.loads(nlri.json())

    assert rendered == {'eor': {'afi': 'ipv4', 'safi': 'unicast'}}


def test_eor_nlri_json_survives_being_put_in_a_list():
    # this is what the API response builder does with every NLRI
    nlris = [EOR.NLRI(AFI.ipv6, SAFI.unicast, Action.ANNOUNCE).json()]

    rendered = json.loads('[ {} ]'.format(', '.join(nlris)))

    assert rendered == [{'eor': {'afi': 'ipv6', 'safi': 'unicast'}}]


def test_eor_update_reported_to_an_api_process_is_json():
    # an EOR carries no action, so the builder does not list it: it takes its own
    # branch, which wrapped the object in a second pair of braces
    for eor in (EOR(AFI.ipv4, SAFI.unicast), EOR(AFI.ipv6, SAFI.unicast)):
        message = str(JSON('6.0.0')._update(eor)['message'])

        rendered = json.loads(message)

        assert rendered == {'eor': {'afi': str(eor.nlris[0].afi), 'safi': 'unicast'}}
