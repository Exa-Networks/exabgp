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


import codecs
import gc
import re
import inspect
import types
import operator
import os
import subprocess
import tempfile
import sys
import itertools

try:
    from types import InstanceType
except ImportError:
    # Python 3.x compatibility
    InstanceType = None


__author__ = "Marius Gedminas (marius@gedmin.as)"
__copyright__ = "Copyright (c) 2008-2015 Marius Gedminas and contributors"
__license__ = "MIT"
__version__ = "2.0.1"
__date__ = "2015-07-28"


try:
    basestring
except NameError:
    # Python 3.x compatibility
    basestring = str

try:
    iteritems = dict.iteritems
except AttributeError:
    # Python 3.x compatibility
    iteritems = dict.items


def count(typename, objects=None):
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


def typestats(objects=None, shortnames=True):
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
        if shortnames:
            typename = _short_typename
        else:
            typename = _long_typename
        stats = {}
        for o in objects:
            n = typename(o)
            stats[n] = stats.get(n, 0) + 1
        return stats
    finally:
        del objects  # clear cyclic references to frame


def most_common_types(limit=10, objects=None, shortnames=True):
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
    stats = sorted(typestats(objects, shortnames=shortnames).items(),
                   key=operator.itemgetter(1), reverse=True)
    if limit:
        stats = stats[:limit]
    return stats


def show_most_common_types(limit=10, objects=None, shortnames=True):
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
    width = max(len(name) for name, count in stats)
    for name, count in stats:
        print('%-*s %i' % (width, name, count))


def show_growth(limit=10, peak_stats={}, shortnames=True):
    """Show the increase in peak object counts since last call.

    Limits the output to ``limit`` largest deltas.  You may set ``limit`` to
    None to see all of them.

    Uses and updates ``peak_stats``, a dictionary from type names to previously
    seen peak object counts.  Usually you don't need to pay attention to this
    argument.

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
    gc.collect()
    stats = typestats(shortnames=shortnames)
    deltas = {}
    for name, count in iteritems(stats):
        old_count = peak_stats.get(name, 0)
        if count > old_count:
            deltas[name] = count - old_count
            peak_stats[name] = count
    deltas = sorted(deltas.items(), key=operator.itemgetter(1),
                    reverse=True)
    if limit:
        deltas = deltas[:limit]
    if deltas:
        width = max(len(name) for name, count in deltas)
        for name, delta in deltas:
            print('%-*s%9d %+9d' % (width, name, stats[name], delta))


def get_leaking_objects(objects=None):
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
        for i in objects:
            ids.difference_update(id(j) for j in gc.get_referents(i))
        # this then is our set of objects without referrers
        return [i for i in objects if id(i) in ids]
    finally:
        del objects, i  # clear cyclic references to frame


def by_type(typename, objects=None):
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


def at(addr):
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


def find_ref_chain(obj, predicate, max_depth=20, extra_ignore=()):
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
    return _find_chain(obj, predicate, gc.get_referents,
                       max_depth=max_depth, extra_ignore=extra_ignore)[::-1]


def find_backref_chain(obj, predicate, max_depth=20, extra_ignore=()):
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
    return _find_chain(obj, predicate, gc.get_referrers,
                       max_depth=max_depth, extra_ignore=extra_ignore)


def show_backrefs(objs, max_depth=3, extra_ignore=(), filter=None, too_many=10,
                  highlight=None, filename=None, extra_info=None,
                  refcounts=False, shortnames=True, output=None):
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
    _show_graph(objs, max_depth=max_depth, extra_ignore=extra_ignore,
                filter=filter, too_many=too_many, highlight=highlight,
                edge_func=gc.get_referrers, swap_source_target=False,
                filename=filename, output=output, extra_info=extra_info,
                refcounts=refcounts, shortnames=shortnames,
                cull_func=is_proper_module)


def show_refs(objs, max_depth=3, extra_ignore=(), filter=None, too_many=10,
              highlight=None, filename=None, extra_info=None,
              refcounts=False, shortnames=True, output=None):
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
    _show_graph(objs, max_depth=max_depth, extra_ignore=extra_ignore,
                filter=filter, too_many=too_many, highlight=highlight,
                edge_func=gc.get_referents, swap_source_target=True,
                filename=filename, extra_info=extra_info, refcounts=refcounts,
                shortnames=shortnames, output=output)


def show_chain(*chains, **kw):
    """Show a chain (or several chains) of object references.

    Useful in combination with :func:`find_ref_chain` or
    :func:`find_backref_chain`, e.g.

        >>> show_chain(find_backref_chain(obj, is_proper_module))

    You can specify if you want that chain traced backwards or forwards
    by passing a ``backrefs`` keyword argument, e.g.

        >>> show_chain(find_ref_chain(obj, is_proper_module),
        ...            backrefs=False)

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
    backrefs = kw.pop('backrefs', True)
    chains = [chain for chain in chains if chain]  # remove empty ones

    def in_chains(x, ids=set(map(id, itertools.chain(*chains)))):
        return id(x) in ids
    max_depth = max(map(len, chains)) - 1
    if backrefs:
        show_backrefs([chain[-1] for chain in chains], max_depth=max_depth,
                      filter=in_chains, **kw)
    else:
        show_refs([chain[0] for chain in chains], max_depth=max_depth,
                  filter=in_chains, **kw)


def is_proper_module(obj):
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
    return (inspect.ismodule(obj) and
            obj is sys.modules.get(getattr(obj, '__name__', None)))


#
# Internal helpers
#

def _find_chain(obj, predicate, edge_func, max_depth=20, extra_ignore=()):
    queue = [obj]
    depth = {id(obj): 0}
    parent = {id(obj): None}
    ignore = set(extra_ignore)
    ignore.add(id(extra_ignore))
    ignore.add(id(queue))
    ignore.add(id(depth))
    ignore.add(id(parent))
    ignore.add(id(ignore))
    ignore.add(id(sys._getframe()))   # this function
    ignore.add(id(sys._getframe(1)))  # find_chain/find_backref_chain
    gc.collect()
    while queue:
        target = queue.pop(0)
        if predicate(target):
            chain = [target]
            while parent[id(target)] is not None:
                target = parent[id(target)]
                chain.append(target)
            return chain
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


def _show_graph(objs, edge_func, swap_source_target,
                max_depth=3, extra_ignore=(), filter=None, too_many=10,
                highlight=None, filename=None, extra_info=None,
                refcounts=False, shortnames=True, output=None,
                cull_func=None):
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    if filename and output:
        raise ValueError('Cannot specify both output and filename.')
    elif output:
        f = output
    elif filename and filename.endswith('.dot'):
        f = codecs.open(filename, 'w', encoding='utf-8')
        dot_filename = filename
    else:
        fd, dot_filename = tempfile.mkstemp(prefix='objgraph-',
                                            suffix='.dot', text=True)
        f = os.fdopen(fd, "w")
        if getattr(f, 'encoding', None):
            # Python 3 will wrap the file in the user's preferred encoding
            # Re-wrap it for utf-8
            import io
            f = io.TextIOWrapper(f.detach(), 'utf-8')
    f.write('digraph ObjectGraph {\n'
            '  node[shape=box, style=filled, fillcolor=white];\n')
    queue = []
    depth = {}
    ignore = set(extra_ignore)
    ignore.add(id(objs))
    ignore.add(id(extra_ignore))
    ignore.add(id(queue))
    ignore.add(id(depth))
    ignore.add(id(ignore))
    ignore.add(id(sys._getframe()))   # this function
    ignore.add(id(sys._getframe().f_locals))
    ignore.add(id(sys._getframe(1)))  # show_refs/show_backrefs
    ignore.add(id(sys._getframe(1).f_locals))
    for obj in objs:
        f.write('  %s[fontcolor=red];\n' % (_obj_node_id(obj)))
        depth[id(obj)] = 0
        queue.append(obj)
        del obj
    gc.collect()
    nodes = 0
    while queue:
        nodes += 1
        # The names "source" and "target" are reversed here because
        # originally there was just show_backrefs() and we were
        # traversing the reference graph backwards.
        target = queue.pop(0)
        tdepth = depth[id(target)]
        f.write('  %s[label="%s"];\n' % (_obj_node_id(target),
                                         _obj_label(target, extra_info,
                                                    refcounts, shortnames)))
        h, s, v = _gradient((0, 0, 1), (0, 0, .3), tdepth, max_depth)
        if inspect.ismodule(target):
            h = .3
            s = 1
        if highlight and highlight(target):
            h = .6
            s = .6
            v = 0.5 + v * 0.5
        f.write('  %s[fillcolor="%g,%g,%g"];\n'
                % (_obj_node_id(target), h, s, v))
        if v < 0.5:
            f.write('  %s[fontcolor=white];\n' % (_obj_node_id(target)))
        if hasattr(getattr(target, '__class__', None), '__del__'):
            f.write('  %s->%s_has_a_del[color=red,style=dotted,'
                    'len=0.25,weight=10];\n' % (_obj_node_id(target),
                                                _obj_node_id(target)))
            f.write('  %s_has_a_del[label="__del__",shape=doublecircle,'
                    'height=0.25,color=red,fillcolor="0,.5,1",fontsize=6];\n'
                    % (_obj_node_id(target)))
        if tdepth >= max_depth:
            continue
        if cull_func is not None and cull_func(target):
            continue
        neighbours = edge_func(target)
        ignore.add(id(neighbours))
        n = 0
        skipped = 0
        for source in neighbours:
            if id(source) in ignore:
                continue
            if filter and not filter(source):
                continue
            if n >= too_many:
                skipped += 1
                continue
            if swap_source_target:
                srcnode, tgtnode = target, source
            else:
                srcnode, tgtnode = source, target
            elabel = _edge_label(srcnode, tgtnode, shortnames)
            f.write('  %s -> %s%s;\n' % (_obj_node_id(srcnode),
                                         _obj_node_id(tgtnode), elabel))
            if id(source) not in depth:
                depth[id(source)] = tdepth + 1
                queue.append(source)
            n += 1
            del source
        del neighbours
        if skipped > 0:
            h, s, v = _gradient((0, 1, 1), (0, 1, .3), tdepth + 1, max_depth)
            if swap_source_target:
                label = "%d more references" % skipped
                edge = "%s->too_many_%s" % (_obj_node_id(target),
                                            _obj_node_id(target))
            else:
                label = "%d more backreferences" % skipped
                edge = "too_many_%s->%s" % (_obj_node_id(target),
                                            _obj_node_id(target))
            f.write('  %s[color=red,style=dotted,len=0.25,weight=10];\n'
                    % edge)
            f.write('  too_many_%s[label="%s",shape=box,height=0.25,'
                    'color=red,fillcolor="%g,%g,%g",fontsize=6];\n'
                    % (_obj_node_id(target), label, h, s, v))
            f.write('  too_many_%s[fontcolor=white];\n'
                    % (_obj_node_id(target)))
    f.write("}\n")
    if output:
        return
    # The file should only be closed if this function was in charge of opening
    # the file.
    f.close()
    print("Graph written to %s (%d nodes)" % (dot_filename, nodes))
    _present_graph(dot_filename, filename)


def _present_graph(dot_filename, filename=None):
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
        print("Spawning graph viewer (xdot)")
        subprocess.Popen(['xdot', dot_filename], close_fds=True)
    elif _program_in_path('dot'):
        if not filename:
            print("Graph viewer (xdot) not found, generating a png instead")
            filename = dot_filename[:-4] + '.png'
        stem, ext = os.path.splitext(filename)
        cmd = ['dot', '-T' + ext[1:], '-o' + filename, dot_filename]
        dot = subprocess.Popen(cmd, close_fds=False)
        dot.wait()
        if dot.returncode != 0:
            # XXX: shouldn't this go to stderr or a log?
            print('dot failed (exit code %d) while executing "%s"'
                  % (dot.returncode, ' '.join(cmd)))
        else:
            print("Image generated as %s" % filename)
    else:
        if not filename:
            print("Graph viewer (xdot) and image renderer (dot) not found,"
                  " not doing anything else")
        else:
            print("Image renderer (dot) not found, not doing anything else")


def _obj_node_id(obj):
    return ('o%d' % id(obj)).replace('-', '_')


def _obj_label(obj, extra_info=None, refcounts=False, shortnames=True):
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


def _quote(s):
    return (s.replace("\\", "\\\\")
             .replace("\"", "\\\"")
             .replace("\n", "\\n")
             .replace("\0", "\\\\0"))


def _get_obj_type(obj):
    objtype = type(obj)
    if type(obj) == InstanceType:
        objtype = obj.__class__
    return objtype


def _short_typename(obj):
    return _get_obj_type(obj).__name__


def _long_typename(obj):
    objtype = _get_obj_type(obj)
    name = objtype.__name__
    module = getattr(objtype, '__module__', None)
    if module:
        return '%s.%s' % (module, name)
    else:
        return name


def _safe_repr(obj):
    try:
        return _short_repr(obj)
    except:
        return '(unrepresentable)'


def _short_repr(obj):
    if isinstance(obj, (type, types.ModuleType, types.BuiltinMethodType,
                        types.BuiltinFunctionType)):
        return obj.__name__
    if isinstance(obj, types.MethodType):
        try:
            if obj.__self__ is not None:
                return obj.__func__.__name__ + ' (bound)'
            else:
                return obj.__func__.__name__
        except AttributeError:  # pragma: nocover
            # Python < 2.6 compatibility
            if obj.im_self is not None:
                return obj.im_func.__name__ + ' (bound)'
            else:
                return obj.im_func.__name__

    if isinstance(obj, types.FrameType):
        return '%s:%s' % (obj.f_code.co_filename, obj.f_lineno)
    if isinstance(obj, (tuple, list, dict, set)):
        return '%d items' % len(obj)
    return repr(obj)[:40]


def _gradient(start_color, end_color, depth, max_depth):
    if max_depth == 0:
        # avoid division by zero
        return start_color
    h1, s1, v1 = start_color
    h2, s2, v2 = end_color
    f = float(depth) / max_depth
    h = h1 * (1-f) + h2 * f
    s = s1 * (1-f) + s2 * f
    v = v1 * (1-f) + v2 * f
    return h, s, v


def _edge_label(source, target, shortnames=True):
    if (isinstance(target, dict) and
            target is getattr(source, '__dict__', None)):
        return ' [label="__dict__",weight=10]'
    if isinstance(source, types.FrameType):
        if target is source.f_locals:
            return ' [label="f_locals",weight=10]'
        if target is source.f_globals:
            return ' [label="f_globals",weight=10]'
    if isinstance(source, types.MethodType):
        try:
            if target is source.__self__:
                return ' [label="__self__",weight=10]'
            if target is source.__func__:
                return ' [label="__func__",weight=10]'
        except AttributeError:  # pragma: nocover
            # Python < 2.6 compatibility
            if target is source.im_self:
                return ' [label="im_self",weight=10]'
            if target is source.im_func:
                return ' [label="im_func",weight=10]'
    if isinstance(source, types.FunctionType):
        for k in dir(source):
            if target is getattr(source, k):
                return ' [label="%s",weight=10]' % _quote(k)
    if isinstance(source, dict):
        for k, v in iteritems(source):
            if v is target:
                if isinstance(k, basestring) and _is_identifier(k):
                    return ' [label="%s",weight=2]' % _quote(k)
                else:
                    if shortnames:
                        tn = _short_typename(k)
                    else:
                        tn = _long_typename(k)
                    return ' [label="%s"]' % _quote(tn + "\n" + _safe_repr(k))
    return ''


_is_identifier = re.compile('[a-zA-Z_][a-zA-Z_0-9]*$').match


def _program_in_path(program):
    # XXX: Consider using distutils.spawn.find_executable or shutil.which
    path = os.environ.get("PATH", os.defpath).split(os.pathsep)
    path = [os.path.join(dir, program) for dir in path]
    path = [True for file in path
            if os.path.isfile(file) or os.path.isfile(file + '.exe')]
    return bool(path)
