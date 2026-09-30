"""The vendored objgraph, as `exabgp server --memory` uses it, typed and compiled with mypyc.

application/server.py prints the most common types, finds the Reactor with by_type(),
and draws what refers to it with show_backrefs(). These run the same calls, interpreted
and against the compiled tree (PYTHONPATH=build/mypyc).
"""

from __future__ import annotations

import gc
import io
import re
import tempfile
from pathlib import Path

import pytest

from exabgp.vendoring import objgraph


class VendoringMarker:
    """A class nothing else in the process is called, so by_type() finds only ours."""

    def method(self) -> None:
        pass


class VendoringGrowth:
    pass


# Compiled, reading an async method of a compiled class (Processes.write_async, ...) makes a
# "Function compiled with mypyc" object whose GC traversal is broken: gc.get_referents() on it
# raises SystemError, and gc.get_referrers() lists it as a referrer of every new object. Once
# any earlier test has touched one, the back references drawn are no longer exact.
COMPILED = not str(objgraph.__file__).endswith('.py')

# Held by this module, so a chain of back references leads from a module to it.
HELD: list[object] = []


def test_show_most_common_types_prints_one_line_per_type(capsys: pytest.CaptureFixture[str]) -> None:
    objgraph.show_most_common_types(limit=5)
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 5
    for line in lines:
        assert re.fullmatch(r'\S+ +\d+', line), line


def test_show_most_common_types_of_nothing_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    objgraph.show_most_common_types(objects=[])
    assert capsys.readouterr().out == ''


def test_by_type_finds_the_instances_by_short_and_long_name() -> None:
    # The markers of the tests before are unreachable, but may still be waiting for gc.
    gc.collect()
    markers = [VendoringMarker(), VendoringMarker()]
    found = objgraph.by_type('VendoringMarker')
    assert len(found) == 2
    assert all(any(item is marker for marker in markers) for item in found)
    assert objgraph.by_type(f'{__name__}.VendoringMarker', objects=markers) == markers
    assert objgraph.count('VendoringMarker', objects=markers) == 2
    assert objgraph.typestats(objects=markers) == {'VendoringMarker': 2}
    assert objgraph.most_common_types(objects=[*markers, []]) == [('VendoringMarker', 2), ('list', 1)]


def test_show_backrefs_as_the_server_calls_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # No viewer and no renderer in PATH, so nothing is spawned: the .dot file is the result.
    monkeypatch.setenv('PATH', '')
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    gc.collect()
    marker = VendoringMarker()
    found = objgraph.by_type('VendoringMarker')
    objgraph.show_backrefs([found], max_depth=2)
    out = capsys.readouterr().out
    assert 'Graph written to' in out
    assert 'not found, not doing anything else' in out
    (dot,) = tmp_path.glob('objgraph-*.dot')
    graph = dot.read_text(encoding='utf-8')
    assert graph.startswith('digraph ObjectGraph {')
    assert graph.rstrip().endswith('}')
    assert f'o{id(found)}[fontcolor=red]' in graph
    assert found == [marker]


@pytest.mark.xfail(
    COMPILED,
    reason='mypyc async method objects report themselves as referrers of every object, once one exists',
    strict=False,
)
def test_show_backrefs_draws_exactly_what_refers_to_the_object() -> None:
    marker = VendoringMarker()
    holder = {'marker': marker}
    output = io.StringIO()
    objgraph.show_backrefs([marker], max_depth=1, output=output)
    graph = output.getvalue()
    # The dict holds the marker under an identifier, so the edge is labelled with it.
    assert f'o{id(holder)} -> o{id(marker)} [label="marker",weight=2];' in graph
    # The list of roots given, and what objgraph builds walking the graph, are left out:
    # the dict is the only referrer drawn. A running frame is no referrer on Python 3.12.
    assert graph.count(' -> ') == 1


def test_show_backrefs_to_a_file_named_dot(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    filename = tmp_path / 'graph.dot'
    objgraph.show_backrefs(VendoringMarker(), max_depth=1, filename=str(filename))
    assert f'Graph written to {filename}' in capsys.readouterr().out
    assert filename.read_text(encoding='utf-8').startswith('digraph ObjectGraph {')


def test_show_backrefs_refuses_both_a_filename_and_an_output() -> None:
    with pytest.raises(ValueError, match='both output and filename'):
        objgraph.show_backrefs([], filename='graph.dot', output=io.StringIO())


def test_show_refs_labels_a_bound_method_and_its_edges() -> None:
    marker = VendoringMarker()
    bound = marker.method
    output = io.StringIO()
    objgraph.show_refs([bound], max_depth=1, output=output)
    graph = output.getvalue()
    assert 'method (bound)' in graph
    assert 'label="__self__"' in graph
    assert 'label="__func__"' in graph


def test_find_backref_chain_leads_from_a_module() -> None:
    marker = VendoringMarker()
    HELD.append(marker)
    try:
        chain = objgraph.find_backref_chain(marker, objgraph.is_proper_module)
    finally:
        HELD.remove(marker)
    assert chain[-1] is marker
    assert objgraph.is_proper_module(chain[0])
    assert len(chain) > 1


def test_find_ref_chain_without_a_match_is_the_object() -> None:
    marker = VendoringMarker()
    assert objgraph.find_ref_chain(marker, lambda x: False, max_depth=1) == [marker]


def test_show_chain_of_nothing_draws_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    objgraph.show_chain([], output=io.StringIO())
    assert capsys.readouterr().out == ''


def test_show_chain_draws_the_chain() -> None:
    marker = VendoringMarker()
    HELD.append(marker)
    try:
        chain = objgraph.find_backref_chain(marker, objgraph.is_proper_module)
        output = io.StringIO()
        objgraph.show_chain(chain, output=output)
    finally:
        HELD.remove(marker)
    assert f'o{id(marker)}[fontcolor=red]' in output.getvalue()


def test_show_growth_reports_what_grew_since_the_last_call(capsys: pytest.CaptureFixture[str]) -> None:
    objgraph.show_growth(limit=None)
    capsys.readouterr()
    grown = [VendoringGrowth() for _ in range(50)]
    objgraph.show_growth(limit=None)
    out = capsys.readouterr().out
    assert re.search(r'^VendoringGrowth +50 +\+50$', out, re.MULTILINE), out
    assert len(grown) == 50


def test_get_leaking_objects_of_nothing_is_nothing() -> None:
    # The original deleted its loop variable in a finally, unbound when there were no
    # objects to loop over, and raised UnboundLocalError instead of returning.
    assert objgraph.get_leaking_objects(objects=[]) == []


def test_get_leaking_objects_finds_what_nothing_refers_to() -> None:
    held = VendoringMarker()
    holder = [held]
    assert objgraph.get_leaking_objects(objects=[holder, held]) == [holder]


def test_at_finds_an_object_by_address() -> None:
    marker = VendoringMarker()
    assert objgraph.at(id(marker)) is marker
