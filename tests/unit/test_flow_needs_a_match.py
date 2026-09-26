"""A flow route with no match is malformed on the wire, so we must not build one.

RFC 8955 4.2 encodes the NLRI value as

    Encoding: <[component]+>

one component or more. The components are individually optional, which is what "a list of
optional components" means; the list is not. The same section closes with

    An NLRI value not encoded as specified here, including an NLRI that contains an unknown
    component type, is considered malformed and error handling according to Section 10 is
    performed.

and section 10 sends that to RFC 7606, which for a FlowSpec NLRI is treat-as-withdraw.

So the "matches everything" reading is a consequence, not a permission. 4.2 also says a packet
matches "the intersection (AND) of all the components present", and the intersection of nothing
is every packet, which is why `then { discard; }` with no match is a discard-all rule. The
grammar forbids the shape existing, so the RFC never asks anyone to honour it as match-all.

`flow.py` already refuses it on the way IN, from a peer, with
"flow NLRI carries no component, which would match every packet". Both trees did. Neither
refused it on the way OUT, so each would announce a shape it would itself drop. This closes
that, at the point where the operator's line number is still known.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).parent.parent.parent

NEIGHBOUR = """
neighbor 127.0.0.1 {
  router-id 1.2.3.4;
  local-address 127.0.0.2;
  local-as 1;
  peer-as 1;
  family { ipv4 flow; }
  flow { %s }
}
"""

NO_MATCH = NEIGHBOUR % 'route test { then { discard; } }'
EMPTY_MATCH = NEIGHBOUR % 'route test { match { } then { discard; } }'
ONE_MATCH = NEIGHBOUR % 'route test { match { source 10.0.0.0/24; } then { discard; } }'
TWO_MATCHES = NEIGHBOUR % 'route test { match { source 10.0.0.0/24; destination 10.1.0.0/24; } then { discard; } }'
RATE_LIMIT = NEIGHBOUR % 'route test { match { protocol tcp; } then { rate-limit 9600; } }'


def validate(tmp_path, text):
    """The real validator as a subprocess, which is what an operator runs.

    PYTHONPATH is dropped: it points at the other tree in this checkout, and leaving it would
    have this test validate the wrong source.
    """
    conf = tmp_path / 'test.conf'
    conf.write_text(text)
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    return subprocess.run(
        [str(ROOT / 'sbin' / 'exabgp'), 'validate', '-nrv', str(conf)],
        capture_output=True,
        text=True,
        env=environ,
        cwd=str(ROOT),
        timeout=180,
    )


@pytest.mark.parametrize('text,shape', [(NO_MATCH, 'no match block'), (EMPTY_MATCH, 'an empty match block')])
def test_a_flow_route_without_a_component_is_refused(tmp_path, text, shape) -> None:
    """The defect: this used to load and announce a one byte NLRI matching every packet."""
    result = validate(tmp_path, text)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, f'{shape} was accepted'
    assert 'at least one match' in combined, combined[-1500:]


def test_the_refusal_names_the_line(tmp_path) -> None:
    """A configuration error which does not say where is most of the way to useless."""
    result = validate(tmp_path, NO_MATCH)

    combined = result.stdout + result.stderr
    assert 'line ' in combined
    assert 'neighbor/flow/route' in combined


def test_it_is_a_configuration_error_and_not_a_traceback(tmp_path) -> None:
    """It used to reach check.py and raise IndexError out of the validator."""
    result = validate(tmp_path, NO_MATCH)

    combined = result.stdout + result.stderr
    assert 'Traceback' not in combined
    assert 'IndexError' not in combined
    assert 'github.com/Exa-Networks/exabgp/issues' not in combined


@pytest.mark.parametrize(
    'text,shape',
    [
        (ONE_MATCH, 'one component'),
        (TWO_MATCHES, 'two components'),
        (RATE_LIMIT, 'a protocol match with rate-limit'),
    ],
)
def test_a_flow_route_with_a_component_still_loads(tmp_path, text, shape) -> None:
    """The control, and it is the point: a refusal which refuses everything is not a fix."""
    result = validate(tmp_path, text)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, f'{shape} stopped loading: {combined[-1500:]}'
    assert 'at least one match' not in combined


def test_every_shipped_flow_configuration_still_validates() -> None:
    """Nothing in etc/ relies on the shape being accepted, and this keeps that true."""
    configurations = sorted(p for p in (ROOT / 'etc' / 'exabgp').glob('*.conf') if 'flow' in p.read_text())
    assert configurations, 'no flow configuration found to check, the scan is looking in the wrong place'

    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    for conf in configurations:
        result = subprocess.run(
            [str(ROOT / 'sbin' / 'exabgp'), 'validate', '-nrv', str(conf)],
            capture_output=True,
            text=True,
            env=environ,
            cwd=str(ROOT),
            timeout=180,
        )
        assert result.returncode == 0, f'{conf.name} stopped validating: {(result.stdout + result.stderr)[-1200:]}'
