#!/usr/bin/env python3
# encoding: utf-8

"""The input_assert rule, which now has enough logic to be wrong quietly

TIGER_STYLE forbids validating peer bytes with `assert`, because `-O` deletes the
statement and the check with it. check_tiger_style enforces it, and the rule grew
from "does this assert name a wire parameter" to a taint analysis, which is the
point at which a gate can start being confidently wrong.

Two defects were found in that taint pass, and neither came from a plant:

  Walking the whole assignment target meant `instance.hostname = data[0]` marked
  `instance` as peer data, so `assert isinstance(instance, HostName)` was reported.
  Assigning to a field of a thing does not make the thing the peer's.

  Whether an attribute of a tainted object counts cuts the other way, and the two
  branches answered it differently on purpose. See the test that says so.

Both were found by the session working main by running the widened rule over
UNMODIFIED source and having to justify every hit. That is a different check from
the ones this series has been trading: a plant tests the case you thought of, the
existing tree tests every case that is already there, and the second set is larger
and was not designed by you.

The equivalent here is thin, because this branch has one assert in src. So the
corpus used instead was tests/ and qa/, 3875 asserts across 2265 functions, of
which 17 are flagged and all 17 are genuinely derived from a wire parameter. That
corpus does NOT contain the attribute-assignment shape, so it could not have found
the first defect and did not: fixed and buggy versions flag the identical 17. The
cases below are what actually pins it.
"""

import ast
import importlib.machinery
import importlib.util
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GATE = ROOT / 'qa' / 'bin' / 'check_tiger_style'


def rule():
    spec = importlib.util.spec_from_loader(
        'check_tiger_style', importlib.machinery.SourceFileLoader('check_tiger_style', str(GATE))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flagged(source):
    """The names the rule reports as asserted-about-input in this source"""
    gate = rule()
    tree = ast.parse(source)
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not gate.wire_parameters(node):
            continue
        names.extend(v.detail.split('asserts about ')[-1] for v in gate.input_asserts(node, 'probe'))
    return sorted(names)


class TestItReportsAnAssertAboutPeerBytes:
    def test_the_wire_parameter_itself(self) -> None:
        assert flagged('def unpack(cls, data):\n    assert len(data) >= 4\n') == ['data']

    def test_a_value_assigned_from_it(self) -> None:
        # the case a name-matching rule misses: same peer bytes, same deletion
        assert flagged('def unpack(cls, data):\n    size = data[0]\n    assert size < 10\n') == ['size']

    def test_a_value_two_assignments_away(self) -> None:
        source = 'def unpack(cls, data):\n    head = data[0]\n    size = head + 1\n    assert size < 10\n'
        assert flagged(source) == ['size']

    def test_a_tuple_unpacked_from_it(self) -> None:
        source = 'def unpack(cls, data):\n    first, second = data[0], data[1]\n    assert first < second\n'
        assert flagged(source) == ['first']

    def test_the_parameter_named_body(self) -> None:
        # header and body are the wire bytes handed to every API encoder, and were
        # absent from the parameter list until this series
        assert flagged('def packets(self, header, body):\n    assert len(body) > 18\n') == ['body']


class TestItStaysQuietAboutOurOwnState:
    def test_a_type_invariant_on_an_object_we_populate(self) -> None:
        # the defect: walking the target made `instance` peer data
        source = 'def unpack(cls, instance, data):\n    instance.hostname = data[0]\n    assert isinstance(instance, HostName)\n'
        assert flagged(source) == []

    def test_a_subscript_target_does_not_taint_its_container(self) -> None:
        source = 'def unpack(cls, store, data):\n    store[0] = data[0]\n    assert isinstance(store, dict)\n'
        assert flagged(source) == []

    def test_something_unrelated_to_the_wire(self) -> None:
        assert flagged('def unpack(cls, data):\n    assert cls.__name__\n') == []

    def test_a_function_taking_no_wire_parameter_is_not_examined(self) -> None:
        assert flagged('def decode(self, encoding):\n    assert encoding in ("utf-8",)\n') == []


class TestTheHolesThisRuleIsKnownToHave:
    """Pinned so they are known rather than discovered, and so closing one is deliberate

    A gate reporting zero is read as "none possible". This is the shape it cannot
    see, stated in its docstring. If somebody closes it, this test fails and the
    docstring gets corrected with it, rather than the gate quietly claiming more
    than it does.

    The second test here is not a hole: it records where this branch is STRICTER
    than main, which is worth pinning for the same reason.
    """

    def test_derivation_by_mutation_is_not_tracked(self) -> None:
        # `labels = []` never mentions data, so appending peer bytes into it leaves
        # it untainted. This was the first plant that made the whole taint pass
        # look decorative
        source = (
            'def unpack(cls, data):\n'
            '    labels = []\n'
            '    labels.append(data[0])\n'
            '    assert len(labels) < 100\n'
        )
        assert flagged(source) == [], 'this hole closed; update the docstring in check_tiger_style'

    def test_peer_data_behind_an_attribute_IS_reported_here(self) -> None:
        """Where this branch deliberately differs from main, and why

        Their rule lets an attribute of a tainted object through, because their src
        holds `assert update._parsed is not None`: `update` is genuinely built from
        the wire, and `_parsed` is a field their own parser sets, so the assertion
        is their invariant rather than a check on peer bytes. A real occurrence
        forced the permissive choice.

        This branch has one assert in src and no such occurrence, so nothing forces
        it, and the stricter reading is the safer default for a rule whose whole
        purpose is that peer validation must not be deleted by -O. The cost is
        symmetrical to theirs: an invariant asserted on a wire-derived object would
        be reported here and would need rewriting as a raise.

        Written as an assertion rather than a comment so the divergence is a
        decision on the record instead of two gates that quietly disagree.
        """
        source = 'def unpack(cls, data):\n    nlri = build(data)\n    assert len(nlri.packed) > 4\n'
        assert flagged(source) == ['nlri']


class TestTheProbeItself:
    def test_the_gate_loads_and_exposes_what_this_file_drives(self) -> None:
        gate = rule()
        for name in ('wire_parameters', 'input_asserts', 'derived_from_wire', 'assigned_names'):
            assert hasattr(gate, name), name

    def test_flagged_can_return_something(self) -> None:
        # every assertion above compares against a list; one that always returned []
        # would satisfy the whole "stays quiet" class and both holes
        assert flagged('def unpack(cls, data):\n    assert len(data) >= 4\n')
