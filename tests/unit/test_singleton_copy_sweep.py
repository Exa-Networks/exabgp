#!/usr/bin/env python3
# encoding: utf-8

"""A singleton compared with `is` must copy to itself

Code all over this tree asks whether a value IS a particular sentinel:

    if self.path_info is PathInfo.NOPATH
    if self.rd is not RouteDistinguisher.NORD
    if nlri.labels is Labels.NOLABEL

Identity is the whole point of those tests, and copy.deepcopy defeats them by
default: it mints a new object, the sentinel stops being the sentinel, and every
one of those branches silently changes answer. The RIB deep copies a change on
the withdraw path, so this is the wire path.

It has happened twice in this series. _NoNextHop had it, and fixing that one did
not lead me to look for the others, so PathInfo.NOPATH still had it and broke
route identity for ipv4 unicast, ipv6 unicast, nlri-mpls and mpls-vpn: a copied
route was not equal to itself and could not be found in a dict keyed on it.

THIS FILE WALKS THE SOURCE rather than listing what I happened to find. A list
goes stale the moment someone adds a sentinel; a sweep does not. That is the
lesson from the session working main, who found two more of these by walking the
AST for the comparison rather than by reading the classes that define it: the
defect is not visible in the file which has it, it is visible in the relationship
between the file that defines the sentinel and the file that compares against it.
"""

import ast
import copy
import importlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SOURCE = ROOT / 'src'

# Ratchet: the number of distinct sentinels the walk must resolve and check.
# A walk which resolves nothing checks nothing and is green.
SENTINEL_FLOOR = 4

# Compared with `is`, but not an instance sentinel this rule applies to:
#   NotImplemented  a builtin, and copy returns it already
#   Action.*        an Enum, which copy returns unchanged by construction
#   states.*        likewise
#   InstanceType    a class object, not an instance
NOT_INSTANCE_SENTINELS = {'NotImplemented', 'True', 'False', 'None', 'Ellipsis'}


def module_name(path):
    return '.'.join(path.relative_to(SOURCE).with_suffix('').parts)


def identity_comparisons():
    """Every `x is NAME` and `x is Some.NAME` in src, with the module it is in"""
    for path in sorted(SOURCE.rglob('*.py')):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for op, comparator in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.Is, ast.IsNot)):
                    continue
                if isinstance(comparator, ast.Attribute) and comparator.attr.isupper():
                    if isinstance(comparator.value, ast.Name):
                        yield path, f'{comparator.value.id}.{comparator.attr}'
                elif isinstance(comparator, ast.Name):
                    if comparator.id[0].isupper() and comparator.id not in NOT_INSTANCE_SENTINELS:
                        yield path, comparator.id


def resolve(path, expression):
    """The object that expression names, seen from the module which compares it"""
    try:
        module = importlib.import_module(module_name(path))
    except Exception:  # noqa: BLE001 - a module which will not import cannot be swept
        return None
    value = module
    for part in expression.split('.'):
        value = getattr(value, part, None)
        if value is None:
            return None
    return value


def instance_sentinels():
    """Resolved sentinels which are plain instances, deduplicated by identity"""
    seen, found = set(), {}
    for path, expression in identity_comparisons():
        value = resolve(path, expression)
        if value is None or isinstance(value, type):
            continue
        # an Enum member is copy-safe by construction, and is not what this is about
        if type(type(value)).__name__ == 'EnumMeta' or type(type(value)).__name__ == 'EnumType':
            continue
        if id(value) in seen:
            continue
        seen.add(id(value))
        found[expression] = value
    return found


SENTINELS = instance_sentinels()
NAMES = sorted(SENTINELS)


class TestTheSweepFoundSomething:
    def test_it_resolves_enough_sentinels(self) -> None:
        assert len(SENTINELS) >= SENTINEL_FLOOR, sorted(SENTINELS)

    def test_the_ones_this_series_fixed_are_among_them(self) -> None:
        # the floor is a number; these are the specific sentinels whose copy
        # hooks were written or repaired here, and a walk which stopped seeing
        # them would still clear the floor
        for expected in ('PathInfo.NOPATH', 'RouteDistinguisher.NORD', 'Labels.NOLABEL'):
            assert expected in SENTINELS, sorted(SENTINELS)

    def test_it_finds_the_comparisons_at_all(self) -> None:
        assert list(identity_comparisons()), 'the AST walk matched nothing, so it proves nothing'


@pytest.mark.parametrize('name', NAMES)
def test_a_shallow_copy_is_the_same_object(name) -> None:
    assert copy.copy(SENTINELS[name]) is SENTINELS[name]


@pytest.mark.parametrize('name', NAMES)
def test_a_deep_copy_is_the_same_object(name) -> None:
    # the one the RIB performs
    assert copy.deepcopy(SENTINELS[name]) is SENTINELS[name]


@pytest.mark.parametrize('name', NAMES)
def test_it_survives_inside_a_container(name) -> None:
    # the shape the RIB actually produces: the sentinel reached through the
    # object holding it, where memo handling is what goes wrong
    assert copy.deepcopy({'held': SENTINELS[name]})['held'] is SENTINELS[name]
    assert copy.deepcopy([SENTINELS[name]])[0] is SENTINELS[name]
