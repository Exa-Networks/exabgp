"""A validator must say what it found, not raise out of itself.

`check_generation` packs a route, re-decodes the bytes and compares. It then indexed
`update.nlris[0]` without checking the list, and a flow route with no match block reaches
exactly that: it packs a FlowSpec NLRI of length zero, which RFC 8955 4.2 makes a match on
every packet, and which does not survive its own decode. The answer was

    File ".../configuration/check.py", line 152, in _check_route_generation
    IndexError: list index out of range

out of `exabgp validate`, whose whole job is to report on a configuration, followed by the
banner asking the operator to open a bug report about their own file. Both trees had it, main
at check.py:200 and this one at 152.

Whether an explicitly empty flow rule should be refused at parse time, rather than accepted as
RFC 8955 match-all and caught here, is a separate question and not settled by this test. What
is settled is that the validator reports rather than crashes, whichever way that goes.
"""

from __future__ import annotations

import os
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).parent.parent.parent

EMPTY_MATCH = """
neighbor 127.0.0.1 {
  router-id 1.2.3.4;
  local-address 127.0.0.2;
  local-as 1;
  peer-as 1;
  family { ipv4 flow; }
  flow { route test { then { discard; } } }
}
"""

GOOD_FLOW = """
neighbor 127.0.0.1 {
  router-id 1.2.3.4;
  local-address 127.0.0.2;
  local-as 1;
  peer-as 1;
  family { ipv4 flow; }
  flow { route test { match { source 10.0.0.0/24; } then { discard; } } }
}
"""


def validate(tmp_path, text):
    """Run the real `exabgp validate`, because the defect was a traceback out of that tool.

    sbin/exabgp is a shell wrapper, not a python file, so it is executed rather than handed to
    an interpreter. PYTHONPATH is dropped: it points at the other tree in this checkout, and
    leaving it would have this test validate the wrong source.
    """
    conf = tmp_path / 'test.conf'
    conf.write_text(text)
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    # logging stays ON: the defect was that the operator got a traceback instead of a report,
    # so a test which silences the report cannot see whether one was made
    environ['exabgp_log_enable'] = 'true'
    return subprocess.run(
        [str(ROOT / 'sbin' / 'exabgp'), 'validate', '-nrv', str(conf)],
        capture_output=True,
        text=True,
        env=environ,
        cwd=str(ROOT),
        timeout=180,
    )


def test_a_route_which_reads_back_no_nlri_is_reported_not_raised(tmp_path) -> None:
    """The defect: an IndexError out of the tool whose job is to report."""
    result = validate(tmp_path, EMPTY_MATCH)

    combined = result.stdout + result.stderr
    assert 'IndexError' not in combined, 'the validator raised out of itself'
    assert 'Traceback' not in combined
    assert 'invalid route' in combined, 'the configuration was not reported as invalid'
    assert 'generated no NLRI' in combined, 'nothing said which route, or why'


def test_the_operator_is_not_asked_to_file_a_bug_about_their_own_config(tmp_path) -> None:
    """The traceback banner invites a bug report, which is the wrong thing to ask here."""
    result = validate(tmp_path, EMPTY_MATCH)

    combined = result.stdout + result.stderr
    assert 'github.com/Exa-Networks/exabgp/issues' not in combined


def test_it_still_fails_rather_than_passing_silently(tmp_path) -> None:
    """Reporting is not accepting: the configuration is still refused."""
    result = validate(tmp_path, EMPTY_MATCH)

    assert result.returncode != 0


def test_a_flow_route_with_a_match_still_validates(tmp_path) -> None:
    """The control. A guard which refuses everything would pass the three tests above."""
    result = validate(tmp_path, GOOD_FLOW)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined[-2000:]
    assert 'generated no NLRI' not in combined
