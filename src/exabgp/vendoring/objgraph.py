"""
Tools for drawing Python object reference graphs with graphviz.

You can find documentation online at https://mg.pov.lt/objgraph/

Copyright (c) 2008-2015 Marius Gedminas <marius@pov.lt> and contributors

Released under the MIT licence.
"""

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

# Changed for ExaBGP: typed for mypy --strict and compiled with mypyc. The Python 2
# branches (old-style instances, im_self/im_func, basestring, iteritems) are gone, and
# the walk no longer skips its own frames. It skipped them because gc.get_referrers()
# returned the frame of a running function as a referrer of its locals. On Python 3.12
# a running frame is not traversed by gc and never appears there, and a function
# compiled by mypyc has no frame at all.

from __future__ import annotations

import gc
import re
import inspect
import types
import operator
import os
import shutil
import subprocess
import tempfile
import sys
import itertools
from collections.abc import Callable
from collections.abc import Sequence
from typing import TextIO


__author__ = 'Marius Gedminas (marius@gedmin.as)'
__copyright__ = 'Copyright (c) 2008-2015 Marius Gedminas and contributors'
__license__ = 'MIT'
__version__ = '2.0.1'
__date__ = '2015-07-28'

# A predicate over any object of the heap: filter, highlight, cull and chain ends.
Predicate = Callable[[object], bool]
# What gc.get_referrers and gc.get_referents look like: the neighbours of an object.
EdgeFunction = Callable[[object], list[object]]

# The peak counts show_growth compares against when its caller keeps none of its own.
_PEAK_STATS: dict[str, int] = {}


def count(typename: str, objects: Sequence[object] | None = None) -> int:
    """Count objects tracked by the garbage collector with a given class name.

    Example:

        >>> count('dict')
        42
        >>> count('MyClass', get_leaking_objects())
        3
        >>> count('mymodule.MyClass')
        2

    Note that the GC does not track simple objects like int or str.

    .. versionchanged:: 1.7
       New parameter: ``objects``.

    .. versionchanged:: 1.8
       Accepts fully-qualified type names (i.e. 'package.module.ClassName')
       as well as short type names (i.e. 'ClassName').

    """
    if objects is None:
        objects = gc.get_objects()
    try:
        if '.' in typename:
            return sum(1 for o in objects if _long_typename(o) == typename)
        else:
            return sum(1 for o in objects if _short_typename(o) == typename)
    finally:
        del objects  # clear cyclic references to frame


def typestats(objects: Sequence[object] | None = None, shortnames: bool = True) -> dict[str, int]:
    """Count the number of instances for each type tracked by the GC.

    Note that the GC does not track simple objects like int or str.

    Note that classes with the same name but defined in different modules
    will be lumped together if ``shortnames`` is True.

    Example:

        >>> typestats()
        {'list': 12041, 'tuple': 10245, ...}
        >>> typestats(get_leaking_objects())
        {'MemoryError': 1, 'tuple': 2795, 'RuntimeError': 1, 'list': 47, ...}

    .. versionadded:: 1.1

    .. versionchanged:: 1.7
       New parameter: ``objects``.

    .. versionchanged:: 1.8
       New parameter: ``shortnames``.

    """
    if objects is None:
        objects = gc.get_objects()
    try:
        typename = _short_typename if shortnames else _long_typename
        stats: dict[str, int] = {}
        for o in objects:
            n = typename(o)
            stats[n] = stats.get(n, 0) + 1
        return stats
    finally:
        del objects  # clear cyclic references to frame


def most_common_types(
    limit: int | None = 10, objects: Sequence[object] | None = None, shortnames: bool = True
) -> list[tuple[str, int]]:
    """Count the names of types with the most instances.

    Returns a list of (type_name, count), sorted most-frequent-first.

    Limits the return value to at most ``limit`` items.  You may set ``limit``
    to None to avoid that.

    The caveats documented in :func:`typestats` apply.

    Example:

        >>> most_common_types(limit=2)
        [('list', 12041), ('tuple', 10245)]

    .. versionadded:: 1.4

    .. versionchanged:: 1.7
       New parameter: ``objects``.

    .. versionchanged:: 1.8
       New parameter: ``shortnames``.

    """
    stats = sorted(typestats(objects, shortnames=shortnames).items(), key=operator.itemgetter(1), reverse=True)
    if limit:
        stats = stats[:limit]
    return stats


def show_most_common_types(
    limit: int | None = 10, objects: Sequence[object] | None = None, shortnames: bool = True
) -> None:
    """Print the table of types of most common instances.

    The caveats documented in :func:`typestats` apply.

    Example:

        >>> show_most_common_types(limit=5)
        tuple                      8959
        function                   2442
        wrapper_descriptor         1048
        dict                       953
        builtin_function_or_method 800

    .. versionadded:: 1.1

    .. versionchanged:: 1.7
       New parameter: ``objects``.

    .. versionchanged:: 1.8
       New parameter: ``shortnames``.

    """
    stats = most_common_types(limit, objects, shortnames=shortnames)
    # max() of nothing raises: an empty list of objects prints an empty table.
    width = max((len(name) for name, _ in stats), default=0)
    for name, number in stats:
        print('%-*s %i' % (width, name, number))


def show_growth(limit: int | None = 10, peak_stats: dict[str, int] | None = None, shortnames: bool = True) -> None:
    """Show the increase in peak object counts since last call.

    Limits the output to ``limit`` largest deltas.  You may set ``limit`` to
    None to see all of them.

    Uses and updates ``peak_stats``, a dictionary from type names to previously
    seen peak object counts.  Usually you don't need to pay attention to this
    argument: without one, a dictionary kept by this module is used, so one
    call compares against the previous one.

    The caveats documented in :func:`typestats` apply.

    Example:

        >>> show_growth()
        wrapper_descriptor       970       +14
        tuple                  12282       +10
        dict                    1922        +7
        ...

    .. versionadded:: 1.5

    .. versionchanged:: 1.8
       New parameter: ``shortnames``.

    """
    # The original used a mutable default argument as the store, a dictionary made once
    # when the function is defined. A module level one is the same thing, said plainly.
    peaks = _PEAK_STATS if peak_stats is None else peak_stats
    gc.collect()
    stats = typestats(shortnames=shortnames)
    growth: dict[str, int] = {}
    for name, number in stats.items():
        old_count = peaks.get(name, 0)
        if number > old_count:
            growth[name] = number - old_count
            peaks[name] = number
    deltas = sorted(growth.items(), key=operator.itemgetter(1), reverse=True)
    if limit:
        deltas = deltas[:limit]
    if deltas:
        width = max(len(name) for name, _ in deltas)
        for name, delta in deltas:
            print('%-*s%9d %+9d' % (width, name, stats[name], delta))


def get_leaking_objects(objects: Sequence[object] | None = None) -> list[object]:
    """Return objects that do not have any referents.

    These could indicate reference-counting bugs in C code.  Or they could
    be legitimate.

    Note that the GC does not track simple objects like int or str.

    .. versionadded:: 1.7
    """
    if objects is None:
        gc.collect()
        objects = gc.get_objects()
    try:
        ids = set(id(i) for i in objects)
        for referrer in objects:
            ids.difference_update(map(id, gc.get_referents(referrer)))
        # this then is our set of objects without referrers
        return [i for i in objects if id(i) in ids]
    finally:
        # The loop variable is not deleted: with no objects it was never bound, and
        # `del` raised UnboundLocalError over the empty result.
        del objects  # clear cyclic references to frame


def by_type(typename: str, objects: Sequence[object] | None = None) -> list[object]:
    """Return objects tracked by the garbage collector with a given class name.

    Example:

        >>> by_type('MyClass')
        [<mymodule.MyClass object at 0x...>]

    Note that the GC does not track simple objects like int or str.

    .. versionchanged:: 1.7
       New parameter: ``objects``.

    .. versionchanged:: 1.8
       Accepts fully-qualified type names (i.e. 'package.module.ClassName')
       as well as short type names (i.e. 'ClassName').

    """
    if objects is None:
        objects = gc.get_objects()
    try:
        if '.' in typename:
            return [o for o in objects if _long_typename(o) == typename]
        else:
            return [o for o in objects if _short_typename(o) == typename]
    finally:
        del objects  # clear cyclic references to frame


def at(addr: int) -> object:
    """Return an object at a given memory address.

    The reverse of id(obj):

        >>> at(id(obj)) is obj
        True

    Note that this function does not work on objects that are not tracked by
    the GC (e.g. ints or strings).
    """
    for o in gc.get_objects():
        if id(o) == addr:
            return o
    return None


def find_ref_chain(
    obj: object, predicate: Predicate, max_depth: int = 20, extra_ignore: Sequence[int] = ()
) -> list[object]:
    """Find a shortest chain of references leading from obj.

    The end of the chain will be some object that matches your predicate.

    ``predicate`` is a function taking one argument and returning a boolean.

    ``max_depth`` limits the search depth.

    ``extra_ignore`` can be a list of object IDs to exclude those objects from
    your search.

    Example:

        >>> find_ref_chain(obj, lambda x: isinstance(x, MyClass))
        [obj, ..., <MyClass object at ...>]

    Returns ``[obj]`` if such a chain could not be found.

    .. versionadded:: 1.7
    """
    return _find_chain(obj, predicate, gc.get_referents, max_depth=max_depth, extra_ignore=extra_ignore)[::-1]


def find_backref_chain(
    obj: object, predicate: Predicate, max_depth: int = 20, extra_ignore: Sequence[int] = ()
) -> list[object]:
    """Find a shortest chain of references leading to obj.

    The start of the chain will be some object that matches your predicate.

    ``predicate`` is a function taking one argument and returning a boolean.

    ``max_depth`` limits the search depth.

    ``extra_ignore`` can be a list of object IDs to exclude those objects from
    your search.

    Example:

        >>> find_backref_chain(obj, is_proper_module)
        [<module ...>, ..., obj]

    Returns ``[obj]`` if such a chain could not be found.

    .. versionchanged:: 1.5
       Returns ``obj`` instead of ``None`` when a chain could not be found.

    """
    return _find_chain(obj, predicate, gc.get_referrers, max_depth=max_depth, extra_ignore=extra_ignore)


def show_backrefs(
    objs: object,
    max_depth: int = 3,
    extra_ignore: Sequence[int] = (),
    filter: Predicate | None = None,
    too_many: int = 10,
    highlight: Predicate | None = None,
    filename: str | None = None,
    extra_info: Callable[[object], object] | None = None,
    refcounts: bool = False,
    shortnames: bool = True,
    output: TextIO | None = None,
) -> None:
    """Generate an object reference graph ending at ``objs``.

    The graph will show you what objects refer to ``objs``, directly and
    indirectly.

    ``objs`` can be a single object, or it can be a list of objects.  If
    unsure, wrap the single object in a new list.

    ``filename`` if specified, can be the name of a .dot or a image
    file, whose extension indicates the desired output format; note
    that output to a specific format is entirely handled by GraphViz:
    if the desired format is not supported, you just get the .dot
    file.  If ``filename`` and ``output`` is not specified, ``show_backrefs``
    will try to produce a .dot file and spawn a viewer (xdot).  If xdot is
    not available, ``show_backrefs`` will convert the .dot file to a
    .png and print its name.

    ``output`` if specified, the GraphViz output will be written to this
    file object. ``output`` and ``filename`` should not both be specified.

    Use ``max_depth`` and ``too_many`` to limit the depth and breadth of the
    graph.

    Use ``filter`` (a predicate) and ``extra_ignore`` (a list of object IDs) to
    remove undesired objects from the graph.

    Use ``highlight`` (a predicate) to highlight certain graph nodes in blue.

    Use ``extra_info`` (a function taking one argument and returning a
    string) to report extra information for objects.

    Specify ``refcounts=True`` if you want to see reference counts.
    These will mostly match the number of arrows pointing to an object,
    but can be different for various reasons.

    Specify ``shortnames=False`` if you want to see fully-qualified type
    names ('package.module.ClassName').  By default you get to see only the
    class name part.

    Examples:

        >>> show_backrefs(obj)
        >>> show_backrefs([obj1, obj2])
        >>> show_backrefs(obj, max_depth=5)
        >>> show_backrefs(obj, filter=lambda x: not inspect.isclass(x))
        >>> show_backrefs(obj, highlight=inspect.isclass)
        >>> show_backrefs(obj, extra_ignore=[id(locals())])

    .. versionchanged:: 1.3
       New parameters: ``filename``, ``extra_info``.

    .. versionchanged:: 1.5
       New parameter: ``refcounts``.

    .. versionchanged:: 1.8
       New parameter: ``shortnames``.

    .. versionchanged:: 2.0
       New parameter: ``output``.

    """
    # For show_backrefs(), it makes sense to stop when reaching a
    # module because you'll end up in sys.modules and explode the
    # graph with useless clutter.  That's why we're specifying
    # cull_func here, but not in show_graph().
    _show_graph(
        objs,
        _GraphOptions(
            edge_func=gc.get_referrers,
            swap_source_target=False,
            max_depth=max_depth,
            too_many=too_many,
            filter=filter,
            highlight=highlight,
            extra_info=extra_info,
            refcounts=refcounts,
            shortnames=shortnames,
            cull_func=is_proper_module,
        ),
        extra_ignore,
        filename,
        output,
    )


def show_refs(
    objs: object,
    max_depth: int = 3,
    extra_ignore: Sequence[int] = (),
    filter: Predicate | None = None,
    too_many: int = 10,
    highlight: Predicate | None = None,
    filename: str | None = None,
    extra_info: Callable[[object], object] | None = None,
    refcounts: bool = False,
    shortnames: bool = True,
    output: TextIO | None = None,
) -> None:
    """Generate an object reference graph starting at ``objs``.

    The graph will show you what objects are reachable from ``objs``, directly
    and indirectly.

    ``objs`` can be a single object, or it can be a list of objects.  If
    unsure, wrap the single object in a new list.

    ``filename`` if specified, can be the name of a .dot or a image
    file, whose extension indicates the desired output format; note
    that output to a specific format is entirely handled by GraphViz:
    if the desired format is not supported, you just get the .dot
    file.  If ``filename`` and ``output`` is not specified, ``show_refs`` will
    try to produce a .dot file and spawn a viewer (xdot).  If xdot is
    not available, ``show_refs`` will convert the .dot file to a
    .png and print its name.

    ``output`` if specified, the GraphViz output will be written to this
    file object. ``output`` and ``filename`` should not both be specified.

    Use ``max_depth`` and ``too_many`` to limit the depth and breadth of the
    graph.

    Use ``filter`` (a predicate) and ``extra_ignore`` (a list of object IDs) to
    remove undesired objects from the graph.

    Use ``highlight`` (a predicate) to highlight certain graph nodes in blue.

    Use ``extra_info`` (a function returning a string) to report extra
    information for objects.

    Specify ``refcounts=True`` if you want to see reference counts.

    Examples:

        >>> show_refs(obj)
        >>> show_refs([obj1, obj2])
        >>> show_refs(obj, max_depth=5)
        >>> show_refs(obj, filter=lambda x: not inspect.isclass(x))
        >>> show_refs(obj, highlight=inspect.isclass)
        >>> show_refs(obj, extra_ignore=[id(locals())])

    .. versionadded:: 1.1

    .. versionchanged:: 1.3
       New parameters: ``filename``, ``extra_info``.

    .. versionchanged:: 1.5
       Follows references from module objects instead of stopping.
       New parameter: ``refcounts``.

    .. versionchanged:: 1.8
       New parameter: ``shortnames``.

    .. versionchanged:: 2.0
       New parameter: ``output``.
    """
    _show_graph(
        objs,
        _GraphOptions(
            edge_func=gc.get_referents,
            swap_source_target=True,
            max_depth=max_depth,
            too_many=too_many,
            filter=filter,
            highlight=highlight,
            extra_info=extra_info,
            refcounts=refcounts,
            shortnames=shortnames,
            cull_func=None,
        ),
        extra_ignore,
        filename,
        output,
    )


def show_chain(
    *chains: Sequence[object],
    backrefs: bool = True,
    highlight: Predicate | None = None,
    extra_info: Callable[[object], object] | None = None,
    refcounts: bool = False,
    shortnames: bool = True,
    filename: str | None = None,
    output: TextIO | None = None,
) -> None:
    """Show a chain (or several chains) of object references.

    Useful in combination with :func:`find_ref_chain` or
    :func:`find_backref_chain`, e.g.

        >>> show_chain(find_backref_chain(obj, is_proper_module))

    You can specify if you want that chain traced backwards or forwards
    by passing a ``backrefs`` keyword argument, e.g.

        >>> show_chain(find_ref_chain(obj, is_proper_module), backrefs=False)

    Ideally this shouldn't matter, but for some objects
    :func:`gc.get_referrers` and :func:`gc.get_referents` are not perfectly
    symmetrical.

    You can specify ``highlight``, ``extra_info``, ``refcounts``,
    ``shortnames``,``filename`` or ``output`` arguments like for
    :func:`show_backrefs` or :func:`show_refs`.

    .. versionadded:: 1.5

    .. versionchanged:: 1.7
       New parameter: ``backrefs``.

    .. versionchanged:: 2.0
       New parameter: ``output``.

    """
    kept = [chain for chain in chains if chain]  # remove empty ones
    if not kept:
        # Nothing to draw. The original raised ValueError, from max() of an empty list.
        return
    ids = set(map(id, itertools.chain(*kept)))

    def in_chains(x: object) -> bool:
        return id(x) in ids

    max_depth = max(map(len, kept)) - 1
    if backrefs:
        show_backrefs(
            [chain[-1] for chain in kept],
            max_depth=max_depth,
            filter=in_chains,
            highlight=highlight,
            extra_info=extra_info,
            refcounts=refcounts,
            shortnames=shortnames,
            filename=filename,
            output=output,
        )
    else:
        show_refs(
            [chain[0] for chain in kept],
            max_depth=max_depth,
            filter=in_chains,
            highlight=highlight,
            extra_info=extra_info,
            refcounts=refcounts,
            shortnames=shortnames,
            filename=filename,
            output=output,
        )


def is_proper_module(obj: object) -> bool:
    """
    Returns ``True`` if ``obj`` can be treated like a garbage collector root.

    That is, if ``obj`` is a module that is in ``sys.modules``.

    >>> import types
    >>> is_proper_module([])
    False
    >>> is_proper_module(types)
    True
    >>> is_proper_module(types.ModuleType('foo'))
    False

    .. versionadded:: 1.8
    """
    if not inspect.ismodule(obj):
        return False
    return obj is sys.modules.get(obj.__name__)


#
# Internal helpers
#


class _GraphOptions:
    """How one graph is drawn: which way the edges go, how deep and how wide, and what is shown."""

    def __init__(
        self,
        *,
        edge_func: EdgeFunction,
        swap_source_target: bool,
        max_depth: int,
        too_many: int,
        filter: Predicate | None,
        highlight: Predicate | None,
        extra_info: Callable[[object], object] | None,
        refcounts: bool,
        shortnames: bool,
        cull_func: Predicate | None,
    ) -> None:
        self.edge_func = edge_func
        # The names "source" and "target" are reversed when this is False, because
        # originally there was just show_backrefs() and it walked the graph backwards.
        self.swap_source_target = swap_source_target
        self.max_depth = max_depth
        self.too_many = too_many
        self.filter = filter
        self.highlight = highlight
        self.extra_info = extra_info
        self.refcounts = refcounts
        self.shortnames = shortnames
        self.cull_func = cull_func


def _find_chain(
    obj: object, predicate: Predicate, edge_func: EdgeFunction, max_depth: int = 20, extra_ignore: Sequence[int] = ()
) -> list[object]:
    queue = [obj]
    depth = {id(obj): 0}
    # None marks the start: it is never a referrer or a referent, gc does not track it.
    parent: dict[int, object | None] = {id(obj): None}
    ignore = set(extra_ignore)
    ignore.add(id(extra_ignore))
    ignore.add(id(queue))
    ignore.add(id(depth))
    ignore.add(id(parent))
    ignore.add(id(ignore))
    gc.collect()
    while queue:
        target = queue.pop(0)
        if predicate(target):
            return _chain_to(target, parent)
        tdepth = depth[id(target)]
        if tdepth < max_depth:
            referrers = edge_func(target)
            ignore.add(id(referrers))
            for source in referrers:
                if id(source) in ignore:
                    continue
                if id(source) not in depth:
                    depth[id(source)] = tdepth + 1
                    parent[id(source)] = target
                    queue.append(source)
    return [obj]  # not found


def _chain_to(target: object, parent: dict[int, object | None]) -> list[object]:
    """The chain from target back to where the search started, following parent."""
    chain = [target]
    link = parent[id(target)]
    # Each object is given a parent once, when it is first reached, so the walk back
    # visits each entry at most once: the bound only fires if parent ever held a loop.
    for _ in range(len(parent)):
        if link is None:
            return chain
        chain.append(link)
        link = parent[id(link)]
    raise RuntimeError('the parents of a reference chain form a loop')


def _show_graph(
    objs: object,
    options: _GraphOptions,
    extra_ignore: Sequence[int] = (),
    filename: str | None = None,
    output: TextIO | None = None,
) -> None:
    roots: list[object] = list(objs) if isinstance(objs, (list, tuple)) else [objs]
    if filename and output:
        raise ValueError('Cannot specify both output and filename.')
    # The caller's list and our copy of it both refer to every root.
    ignore = set(extra_ignore)
    ignore.update((id(objs), id(roots), id(extra_ignore)))
    if output:
        _write_graph(output, roots, options, ignore)
        return
    out, dot_filename = _open_dot(filename)
    # The file is only closed when this function was in charge of opening it.
    try:
        nodes = _write_graph(out, roots, options, ignore)
    finally:
        out.close()
    print('Graph written to %s (%d nodes)' % (dot_filename, nodes))
    _present_graph(dot_filename, filename)


def _open_dot(filename: str | None) -> tuple[TextIO, str]:
    """The file the .dot source is written to, and its name: filename, or a temporary file."""
    if filename and filename.endswith('.dot'):
        return open(filename, 'w', encoding='utf-8'), filename
    fd, dot_filename = tempfile.mkstemp(prefix='objgraph-', suffix='.dot', text=True)
    return os.fdopen(fd, 'w', encoding='utf-8'), dot_filename


def _write_graph(out: TextIO, roots: list[object], options: _GraphOptions, ignore: set[int]) -> int:
    """Walk the graph breadth first from roots, write it to out, and return how many nodes it has."""
    out.write('digraph ObjectGraph {\n  node[shape=box, style=filled, fillcolor=white];\n')
    queue: list[object] = []
    depth: dict[int, int] = {}
    ignore.update((id(queue), id(depth), id(ignore)))
    for root in roots:
        out.write('  %s[fontcolor=red];\n' % (_obj_node_id(root)))
        depth[id(root)] = 0
        queue.append(root)
    gc.collect()
    nodes = 0
    # Bounded by the heap: an object is queued once, when depth first records it.
    while queue:
        nodes += 1
        target = queue.pop(0)
        tdepth = depth[id(target)]
        _write_node(out, target, tdepth, options)
        if tdepth >= options.max_depth:
            continue
        if options.cull_func is not None and options.cull_func(target):
            continue
        neighbours = options.edge_func(target)
        ignore.add(id(neighbours))
        skipped = _write_edges(out, target, neighbours, options, ignore, tdepth + 1, depth, queue)
        if skipped > 0:
            _write_skipped(out, target, skipped, tdepth + 1, options)
    out.write('}\n')
    return nodes


def _write_node(out: TextIO, target: object, tdepth: int, options: _GraphOptions) -> None:
    node = _obj_node_id(target)
    label = _obj_label(target, options.extra_info, options.refcounts, options.shortnames)
    out.write('  %s[label="%s"];\n' % (node, label))
    h, s, v = _gradient((0.0, 0.0, 1.0), (0.0, 0.0, 0.3), tdepth, options.max_depth)
    if inspect.ismodule(target):
        h = 0.3
        s = 1.0
    if options.highlight and options.highlight(target):
        h = 0.6
        s = 0.6
        v = 0.5 + v * 0.5
    out.write('  %s[fillcolor="%g,%g,%g"];\n' % (node, h, s, v))
    if v < 0.5:
        out.write('  %s[fontcolor=white];\n' % (node))
    if hasattr(getattr(target, '__class__', None), '__del__'):
        out.write('  %s->%s_has_a_del[color=red,style=dotted,len=0.25,weight=10];\n' % (node, node))
        out.write(
            '  %s_has_a_del[label="__del__",shape=doublecircle,'
            'height=0.25,color=red,fillcolor="0,.5,1",fontsize=6];\n' % (node)
        )


def _write_edges(
    out: TextIO,
    target: object,
    neighbours: list[object],
    options: _GraphOptions,
    ignore: set[int],
    next_depth: int,
    depth: dict[int, int],
    queue: list[object],
) -> int:
    """Write the edges between target and its neighbours, queue the new ones, return how many were left out."""
    shown = 0
    skipped = 0
    for source in neighbours:
        if id(source) in ignore:
            continue
        if options.filter and not options.filter(source):
            continue
        if shown >= options.too_many:
            skipped += 1
            continue
        if options.swap_source_target:
            srcnode, tgtnode = target, source
        else:
            srcnode, tgtnode = source, target
        elabel = _edge_label(srcnode, tgtnode, options.shortnames)
        out.write('  %s -> %s%s;\n' % (_obj_node_id(srcnode), _obj_node_id(tgtnode), elabel))
        if id(source) not in depth:
            depth[id(source)] = next_depth
            queue.append(source)
        shown += 1
    return skipped


def _write_skipped(out: TextIO, target: object, skipped: int, next_depth: int, options: _GraphOptions) -> None:
    node = _obj_node_id(target)
    h, s, v = _gradient((0.0, 1.0, 1.0), (0.0, 1.0, 0.3), next_depth, options.max_depth)
    if options.swap_source_target:
        label = '%d more references' % skipped
        edge = '%s->too_many_%s' % (node, node)
    else:
        label = '%d more backreferences' % skipped
        edge = 'too_many_%s->%s' % (node, node)
    out.write('  %s[color=red,style=dotted,len=0.25,weight=10];\n' % edge)
    out.write(
        '  too_many_%s[label="%s",shape=box,height=0.25,'
        'color=red,fillcolor="%g,%g,%g",fontsize=6];\n' % (node, label, h, s, v)
    )
    out.write('  too_many_%s[fontcolor=white];\n' % (node))


def _present_graph(dot_filename: str, filename: str | None = None) -> None:
    """Present a .dot file to the user in the requested fashion.

    If ``filename`` is provided, runs ``dot`` to convert the .dot file
    into the desired format, determined by the filename extension.

    If ``filename`` is not provided, tries to launch ``xdot``, a
    graphical .dot file viewer.  If ``xdot`` is not present on the system,
    converts the graph to a PNG.
    """
    if filename == dot_filename:
        # nothing to do, the user asked for a .dot file and got it
        return
    if not filename and _program_in_path('xdot'):
        print('Spawning graph viewer (xdot)')
        subprocess.Popen(['xdot', dot_filename], close_fds=True)
    elif _program_in_path('dot'):
        if not filename:
            print('Graph viewer (xdot) not found, generating a png instead')
            filename = dot_filename[:-4] + '.png'
        stem, ext = os.path.splitext(filename)
        cmd = ['dot', '-T' + ext[1:], '-o' + filename, dot_filename]
        dot = subprocess.Popen(cmd, close_fds=False)
        dot.wait()
        if dot.returncode != 0:
            # XXX: shouldn't this go to stderr or a log?
            print('dot failed (exit code %d) while executing "%s"' % (dot.returncode, ' '.join(cmd)))
        else:
            print('Image generated as %s' % filename)
    else:
        if not filename:
            print('Graph viewer (xdot) and image renderer (dot) not found, not doing anything else')
        else:
            print('Image renderer (dot) not found, not doing anything else')


def _obj_node_id(obj: object) -> str:
    return ('o%d' % id(obj)).replace('-', '_')


def _obj_label(
    obj: object, extra_info: Callable[[object], object] | None = None, refcounts: bool = False, shortnames: bool = True
) -> str:
    if shortnames:
        label = [_short_typename(obj)]
    else:
        label = [_long_typename(obj)]
    if refcounts:
        label[0] += ' [%d]' % (sys.getrefcount(obj) - 4)
        # Why -4?  To ignore the references coming from
        #   obj_label's frame (obj)
        #   show_graph's frame (target variable)
        #   sys.getrefcount()'s argument
        #   something else that doesn't show up in gc.get_referrers()
    label.append(_safe_repr(obj))
    if extra_info:
        label.append(str(extra_info(obj)))
    return _quote('\n'.join(label))


def _quote(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\0', '\\\\0')


# Python 2 had old-style instances, whose type() was InstanceType and whose class was only
# known from __class__. The type() of every Python 3 object is its class.


def _short_typename(obj: object) -> str:
    return type(obj).__name__


def _long_typename(obj: object) -> str:
    objtype = type(obj)
    name = objtype.__name__
    module = getattr(objtype, '__module__', None)
    if module:
        return '%s.%s' % (module, name)
    else:
        return name


def _safe_repr(obj: object) -> str:
    try:
        return _short_repr(obj)
    except Exception:
        # Any repr() may raise, and one label is not worth losing the whole graph over.
        return '(unrepresentable)'


def _short_repr(obj: object) -> str:
    if isinstance(obj, (type, types.ModuleType, types.BuiltinMethodType, types.BuiltinFunctionType)):
        return obj.__name__
    if isinstance(obj, types.MethodType):
        # A Python 3 method object is always bound: an unbound method is the function itself.
        return obj.__name__ + ' (bound)'
    if isinstance(obj, types.FrameType):
        return '%s:%s' % (obj.f_code.co_filename, obj.f_lineno)
    if isinstance(obj, (tuple, list, dict, set)):
        return '%d items' % len(obj)
    return repr(obj)[:40]


def _gradient(
    start_color: tuple[float, float, float], end_color: tuple[float, float, float], depth: int, max_depth: int
) -> tuple[float, float, float]:
    if max_depth == 0:
        # avoid division by zero
        return start_color
    h1, s1, v1 = start_color
    h2, s2, v2 = end_color
    f = float(depth) / max_depth
    h = h1 * (1 - f) + h2 * f
    s = s1 * (1 - f) + s2 * f
    v = v1 * (1 - f) + v2 * f
    return h, s, v


def _edge_label(source: object, target: object, shortnames: bool = True) -> str:
    if isinstance(target, dict) and target is getattr(source, '__dict__', None):
        return ' [label="__dict__",weight=10]'
    if isinstance(source, types.FrameType):
        if target is source.f_locals:
            return ' [label="f_locals",weight=10]'
        if target is source.f_globals:
            return ' [label="f_globals",weight=10]'
    if isinstance(source, types.MethodType):
        if target is source.__self__:
            return ' [label="__self__",weight=10]'
        if target is source.__func__:
            return ' [label="__func__",weight=10]'
    if isinstance(source, types.FunctionType):
        for k in dir(source):
            if target is getattr(source, k):
                return ' [label="%s",weight=10]' % _quote(k)
    if isinstance(source, dict):
        return _dict_edge_label(source, target, shortnames)
    return ''


def _dict_edge_label(source: dict[object, object], target: object, shortnames: bool) -> str:
    """The label of the edge from a dict to target: the key which holds it."""
    for k, v in source.items():
        if v is target:
            if isinstance(k, str) and _IDENTIFIER.match(k):
                return ' [label="%s",weight=2]' % _quote(k)
            if shortnames:
                tn = _short_typename(k)
            else:
                tn = _long_typename(k)
            return ' [label="%s"]' % _quote(tn + '\n' + _safe_repr(k))
    return ''


_IDENTIFIER = re.compile('[a-zA-Z_][a-zA-Z_0-9]*$')


def _program_in_path(program: str) -> bool:
    return shutil.which(program) is not None
