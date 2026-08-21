#!/usr/bin/env python3
# encoding: utf-8

"""The copy hooks are part of the public surface, so hold them to their protocol

copy.copy(x) calls x.__copy__() with NO argument and copy.deepcopy(x) calls
x.__deepcopy__(memo) with one. A hook whose signature disagrees raises instead of
copying, and nothing notices until something copies that object.

_NoNextHop.__copy__ took an extra parameter and had never been called. It is not
reachable from src today, the only copy.copy() there is of a Neighbor, but it is
a dunder a library user can reach and the fix is a signature.

The RIB deep-copies a change on the withdraw path (rib/outgoing.py), so the
deepcopy half IS on the wire path and is not hypothetical.
"""

import copy

import pytest

from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.protocol.ip import NoNextHop


class TestTheSingletonStaysItself:
    """Two no-nexthops would compare unequal and break every `is NoNextHop`"""

    def test_deepcopy_returns_the_singleton(self) -> None:
        assert copy.deepcopy(NoNextHop) is NoNextHop

    def test_copy_returns_the_singleton(self) -> None:
        # this raised TypeError: __copy__() missing 1 required positional argument
        assert copy.copy(NoNextHop) is NoNextHop

    def test_deepcopy_inside_a_container_returns_the_singleton(self) -> None:
        # the shape the RIB actually produces: the nexthop is a field of a change
        holder = {'nexthop': NoNextHop, 'other': [NoNextHop]}
        copied = copy.deepcopy(holder)
        assert copied['nexthop'] is NoNextHop
        assert copied['other'][0] is NoNextHop


class TestTheRouteDistinguisherCopies:
    FILLED = RouteDistinguisher(b'\x00\x01\x02\x03\x04\x05\x06\x07')

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy])
    def test_a_real_rd_keeps_every_field(self, duplicate) -> None:
        # by value on the whole object, not by a proxy like index(): a copy which
        # drops a field still compares equal on anything the key does not include
        copied = duplicate(self.FILLED)
        assert copied == self.FILLED
        assert copied.rd == self.FILLED.rd
        assert str(copied) == str(self.FILLED)
        assert copied.json() == self.FILLED.json()

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy])
    def test_the_nord_singleton_stays_itself(self, duplicate) -> None:
        assert duplicate(RouteDistinguisher.NORD) is RouteDistinguisher.NORD

    def test_the_copy_is_a_distinct_object(self) -> None:
        assert copy.deepcopy(self.FILLED) is not self.FILLED

    def test_sharing_the_immutable_bytes_is_correct(self) -> None:
        # NOT an anti-sharing assertion: the packed bytes are immutable, sharing
        # them is what makes the copy cheap, and asserting nothing is shared
        # fails on classes which are right
        assert copy.deepcopy(self.FILLED).rd == self.FILLED.rd


class TestTheNopathSingletonStaysItself:
    """index() tests it with `is`, so a copy which mints a new object moves the route

    INET.index(), Label.index() and IPVPN.index() all read

        addpath = b'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack()

    so a NOPATH which stopped being NOPATH turned b'no-pi' into four zero bytes
    in the index. The deepcopied route then did not equal its original, hashed
    differently, and could not be found in a dict keyed on it. The RIB deep
    copies a change on the withdraw path, so this is on the wire path: ipv4 and
    ipv6 unicast, nlri-mpls and mpls-vpn were all affected.

    Same defect as _NoNextHop above, in a second singleton, found by asserting
    the identity contract across every family rather than by reading this class.
    """

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy], ids=['copy', 'deepcopy'])
    def test_the_singleton_copies_to_itself(self, duplicate) -> None:
        assert duplicate(PathInfo.NOPATH) is PathInfo.NOPATH

    def test_deepcopy_inside_a_container_returns_the_singleton(self) -> None:
        # the shape the RIB actually produces: the singleton reached through the
        # object holding it, where memo handling is what goes wrong
        assert copy.deepcopy({'pi': PathInfo.NOPATH})['pi'] is PathInfo.NOPATH
        assert copy.deepcopy([PathInfo.NOPATH])[0] is PathInfo.NOPATH

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy], ids=['copy', 'deepcopy'])
    def test_a_real_path_info_is_copied_not_shared(self, duplicate) -> None:
        # returning self unconditionally would pass every assertion above and is
        # wrong: only the singleton is a singleton
        original = PathInfo(integer=42)
        made = duplicate(original)
        assert made is not original
        assert made == original
        assert made.pack() == original.pack()

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy], ids=['copy', 'deepcopy'])
    def test_a_real_path_info_is_not_mistaken_for_the_singleton(self, duplicate) -> None:
        assert duplicate(PathInfo(integer=42)) is not PathInfo.NOPATH

    def test_comparing_with_something_else_answers(self) -> None:
        # __eq__ read other.path_info with nothing checking what other was
        assert (PathInfo(integer=1) == 42) is False
        assert (PathInfo(integer=1) != 42) is True


class TestTheHooksCopyStateRatherThanNamedAttributes:
    """Fixing a specific bug with a specific mechanism is how it comes back

    The default copy carries the whole __dict__ and respects subclasses. Every
    hook written in this series replaced that with a constructor call naming the
    attributes it knew about:

        return PathInfo(packed=self.path_info)
        return RouteDistinguisher(self.rd)

    which is a general mechanism traded for a specific one, while fixing a bug
    that a specific mechanism caused. Nothing is broken today, because none of
    these classes has a second attribute or a subclass, and that is exactly the
    condition under which the next person adds one and nobody revisits the copy.

    Reported by the session working main, who found the same property in their own
    fix for the route_d loss: the fix carried route_d BY NAME, one attribute later
    and the same bug returns in the same method.
    """

    CLASSES = None  # filled below, after the imports it needs

    @staticmethod
    def real_values():
        from exabgp.bgp.message.update.nlri.qualifier.labels import Labels

        return [
            ('PathInfo', PathInfo(integer=42)),
            ('Labels', Labels([16, 24])),
            ('RouteDistinguisher', RouteDistinguisher(bytes(8))),
        ]

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy], ids=['copy', 'deepcopy'])
    def test_a_real_value_keeps_its_class(self, duplicate) -> None:
        for name, value in self.real_values():
            assert type(duplicate(value)) is type(value), name

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy], ids=['copy', 'deepcopy'])
    def test_a_subclass_copies_as_itself(self, duplicate) -> None:
        # naming the class rather than type(self) turns a subclass into its base
        class Marked(PathInfo):
            pass

        original = Marked(integer=7)
        assert type(duplicate(original)) is Marked

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy], ids=['copy', 'deepcopy'])
    def test_an_attribute_the_hook_does_not_know_about_travels(self, duplicate) -> None:
        # the property that makes this general: a field added later needs no edit
        # here. Naming the attributes is what silently drops it.
        original = PathInfo(integer=7)
        original.added_later = 'carried'
        assert getattr(duplicate(original), 'added_later', None) == 'carried'

    def test_deepcopy_does_not_share_the_values(self) -> None:
        # _packed is immutable bytes today, so this cannot be observed yet; it is
        # asserted because a mutable attribute added later would otherwise be
        # shared between a route and its copy
        original = PathInfo(integer=7)
        original.mutable = ['shared?']
        duplicate = copy.deepcopy(original)
        duplicate.mutable.append('no')
        assert original.mutable == ['shared?']


class TestEveryCopyHookInTheTree:
    """Walk the source for copy hooks rather than listing the three I fixed

    I fixed PathInfo, Labels and RouteDistinguisher because they were the ones I
    had written or had just been told about. That is scope set by AUTHORSHIP, and
    it is only complete here by luck: 5.0 has four copy hooks in total. The
    session working main scoped their own review the same way, to their last ten
    commits, and missed a hook which had been in the tree the whole time one
    function along.

    So this walks for the hooks instead of naming them.

    ONE CAVEAT THIS SWEEP ENCODES. Copying __dict__ is right for a class which
    HAS one and wrong for a slotted class, where it copies nothing at all. 5.0
    has exactly one slotted class and it has no copy hooks, so __dict__ is
    correct for all four today. main is the opposite: ten of its hooks name their
    slots, which is the only way to copy a class with no __dict__. The same
    finding has opposite fixes on the two branches, and the assertion below is
    about the PROPERTY, state and class survive a copy, rather than the mechanism.
    """

    @staticmethod
    def template_instance(module, klass):
        """A well formed instance to clone, rather than a bare __new__

        __new__ skips __init__, so the object has none of the attributes its own
        __eq__ reads: RouteDistinguisher.__copy__ compares against NORD, which
        reads self.rd, and the probe raised AttributeError before reaching the
        assertion. Every one of these classes keeps a canonical instance as a
        class or module attribute, so that is used as the template and the probe
        is added to a copy of ITS state.
        """
        for holder in (klass, module):
            for name in dir(holder):
                if name.startswith('__'):
                    continue
                value = getattr(holder, name, None)
                if isinstance(value, klass):
                    return value
        return None

    @staticmethod
    def classes_with_hooks():
        import ast
        import importlib
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent.parent / 'src'
        found = []
        for path in sorted(root.rglob('*.py')):
            try:
                tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                methods = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                if not ({'__copy__', '__deepcopy__'} & methods):
                    continue
                module_name = '.'.join(path.relative_to(root).with_suffix('').parts)
                try:
                    module = importlib.import_module(module_name)
                except Exception:  # noqa: BLE001 - a module which will not import cannot be swept
                    continue
                klass = getattr(module, node.name, None)
                if klass is not None:
                    found.append((f'{module_name}.{node.name}', klass, module))
        return found

    HOOK_FLOOR = 4  # ratchet: a walk which finds nothing asserts nothing

    def test_the_walk_finds_the_hooks(self) -> None:
        found = self.classes_with_hooks()
        assert len(found) >= self.HOOK_FLOOR, [name for name, _k, _m in found]

    def test_none_of_them_copies_nothing(self) -> None:
        """A hook which returns an object with no state is the failure to catch

        Copying __dict__ on a slotted class does exactly that, silently. So does
        naming an attribute the class no longer has. Either way the copy is a
        husk, and this is the assertion which sees it regardless of which
        mechanism the hook chose.
        """
        empty, checked = [], 0
        for name, klass, module in self.classes_with_hooks():
            template = self.template_instance(module, klass)
            if template is None or not hasattr(template, '__dict__'):
                continue  # slotted, or no canonical instance: a different check
            instance = klass.__new__(klass)
            instance.__dict__.update(template.__dict__)
            instance.__dict__['probe'] = 'carried'
            checked += 1
            for duplicate in (copy.copy, copy.deepcopy):
                made = duplicate(instance)
                if made is instance:
                    continue  # a singleton copying to itself, which is correct
                if made is template:
                    # canonicalisation: RouteDistinguisher tests its singleton
                    # with == rather than is, so a separately built RD equal to
                    # NORD copies TO NORD. That is deliberate and it helps the
                    # twenty `is NORD` sites, because an equal-but-separate RD
                    # becomes the singleton rather than staying a lookalike.
                    # The probe attribute cannot survive it, and no such
                    # attribute can exist while rd is the only field.
                    continue
                if getattr(made, 'probe', None) != 'carried':
                    empty.append(f'{name} via {duplicate.__name__}')
        assert not empty, f'these copies lose the object state: {empty}'
        assert checked >= self.HOOK_FLOOR - 1, f'only exercised {checked} hooks'

    def test_none_of_them_changes_class(self) -> None:
        wrong = []
        for name, klass, module in self.classes_with_hooks():
            template = self.template_instance(module, klass)
            if template is None or not hasattr(template, '__dict__'):
                continue
            instance = klass.__new__(klass)
            instance.__dict__.update(template.__dict__)
            for duplicate in (copy.copy, copy.deepcopy):
                made = duplicate(instance)
                if made is not instance and type(made) is not klass:
                    wrong.append(f'{name} via {duplicate.__name__} -> {type(made).__name__}')
        assert not wrong, wrong


class TestTheRouteDistinguisherCanonicalises:
    """It tests its singleton with == where the others use `is`, on purpose

    A RouteDistinguisher built separately but equal to NORD copies TO NORD. The
    other three singletons test identity, so an equal-but-separate value stays
    separate. The difference is deliberate here and it points the safe way: the
    twenty `is RouteDistinguisher.NORD` sites in src see the singleton after a
    copy rather than a lookalike which would answer False.

    Pinned because the copy sweep flags it, and because someone reading the three
    hooks side by side will see the inconsistency and want to make them match.
    Making them match in the `is` direction would turn twenty identity tests into
    tests which can now fail on a copied route.
    """

    def test_an_equal_route_distinguisher_copies_to_the_singleton(self) -> None:
        made = RouteDistinguisher(b'')
        assert made is not RouteDistinguisher.NORD
        assert made == RouteDistinguisher.NORD
        assert copy.copy(made) is RouteDistinguisher.NORD
        assert copy.deepcopy(made) is RouteDistinguisher.NORD

    def test_a_real_route_distinguisher_does_not(self) -> None:
        # the canonicalisation must only reach values which ARE the empty one
        made = RouteDistinguisher(bytes(8))
        assert copy.deepcopy(made) is not RouteDistinguisher.NORD
        assert copy.deepcopy(made) == made
