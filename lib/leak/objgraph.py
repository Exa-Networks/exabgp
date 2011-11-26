"""
Ad-hoc tools for drawing Python object reference graphs with graphviz.

This module is more useful as a repository of sample code and ideas, than
as a finished product.  For documentation and background, read

  http://mg.pov.lt/blog/hunting-python-memleaks.html
  http://mg.pov.lt/blog/python-object-graphs.html
  http://mg.pov.lt/blog/object-graphs-with-graphviz.html

in that order.  Then use pydoc to read the docstrings, as there were
improvements made since those blog posts.

Copyright (c) 2008 Marius Gedminas <marius@pov.lt>

Released under the MIT licence.


Changes
=======

1.1dev (2008-09-05)
-------------------

New function: show_refs() for showing forward references.

New functions: typestats() and show_most_common_types().

Object boxes are less crammed with useless information (such as IDs).

Spawns xdot if it is available.
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

__author__ = "Marius Gedminas (marius@gedmin.as)"
__copyright__ = "Copyright (c) 2008 Marius Gedminas"
__license__ = "MIT"
__version__ = "1.1dev"
__date__ = "2008-09-05"


import gc
import inspect
import types
import weakref
import operator
import os


def count(typename):
    """Count objects tracked by the garbage collector with a given class name.

    Example:

        >>> count('dict')
        42
        >>> count('MyClass')
        3

    Note that the GC does not track simple objects like int or str.
    """
    return sum(1 for o in gc.get_objects() if type(o).__name__ == typename)


def typestats():
    """Count the number of instances for each type tracked by the GC.

    Note that the GC does not track simple objects like int or str.

    Note that classes with the same name but defined in different modules
    will be lumped together.
    """
    stats = {}
    for o in gc.get_objects():
        stats.setdefault(type(o).__name__, 0)
        stats[type(o).__name__] += 1
    return stats


def show_most_common_types(limit=10):
    """Count the names of types with the most instances.

    Note that the GC does not track simple objects like int or str.

    Note that classes with the same name but defined in different modules
    will be lumped together.
    """
    stats = sorted(typestats().items(), key=operator.itemgetter(1),
                   reverse=True)
    if limit:
        stats = stats[:limit]
    width = max(len(name) for name, count in stats)
    for name, count in stats[:limit]:
        print name.ljust(width), count


def by_type(typename):
    """Return objects tracked by the garbage collector with a given class name.

    Example:

        >>> by_type('MyClass')
        [<mymodule.MyClass object at 0x...>]

    Note that the GC does not track simple objects like int or str.
    """
    return [o for o in gc.get_objects() if type(o).__name__ == typename]


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


def find_backref_chain(obj, predicate, max_depth=20, extra_ignore=()):
    """Find a shortest chain of references leading to obj.

    The start of the chain will be some object that matches your predicate.

    ``max_depth`` limits the search depth.

    ``extra_ignore`` can be a list of object IDs to exclude those objects from
    your search.

    Example:

        >>> find_backref_chain(obj, inspect.ismodule)
        [<module ...>, ..., obj]

    Returns None if such a chain could not be found.
    """
    queue = [obj]
    depth = {id(obj): 0}
    parent = {id(obj): None}
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
            chain = [target]
            while parent[id(target)] is not None:
                target = parent[id(target)]
                chain.append(target)
            return chain
        tdepth = depth[id(target)]
        if tdepth < max_depth:
            referrers = gc.get_referrers(target)
            ignore.add(id(referrers))
            for source in referrers:
                if inspect.isframe(source) or id(source) in ignore:
                    continue
                if id(source) not in depth:
                    depth[id(source)] = tdepth + 1
                    parent[id(source)] = target
                    queue.append(source)
    return None # not found


def show_backrefs(objs, max_depth=3, extra_ignore=(), filter=None, too_many=10,
                  highlight=None):
    """Generate an object reference graph ending at ``objs``

    The graph will show you what objects refer to ``objs``, directly and
    indirectly.

    ``objs`` can be a single object, or it can be a list of objects.

    Produces a Graphviz .dot file and spawns a viewer (xdot) if one is
    installed, otherwise converts the graph to a .png image.

    Use ``max_depth`` and ``too_many`` to limit the depth and breadth of the
    graph.

    Use ``filter`` (a predicate) and ``extra_ignore`` (a list of object IDs) to
    remove undesired objects from the graph.

    Use ``highlight`` (a predicate) to highlight certain graph nodes in blue.

    Examples:

        >>> show_backrefs(obj)
        >>> show_backrefs([obj1, obj2])
        >>> show_backrefs(obj, max_depth=5)
        >>> show_backrefs(obj, filter=lambda x: not inspect.isclass(x))
        >>> show_backrefs(obj, highlight=inspect.isclass)
        >>> show_backrefs(obj, extra_ignore=[id(locals())])

    """
    show_graph(objs, max_depth=max_depth, extra_ignore=extra_ignore,
               filter=filter, too_many=too_many, highlight=highlight,
               edge_func=gc.get_referrers, swap_source_target=False)


def show_refs(objs, max_depth=3, extra_ignore=(), filter=None, too_many=10,
              highlight=None):
    """Generate an object reference graph starting at ``objs``

    The graph will show you what objects are reachable from ``objs``, directly
    and indirectly.

    ``objs`` can be a single object, or it can be a list of objects.

    Produces a Graphviz .dot file and spawns a viewer (xdot) if one is
    installed, otherwise converts the graph to a .png image.

    Use ``max_depth`` and ``too_many`` to limit the depth and breadth of the
    graph.

    Use ``filter`` (a predicate) and ``extra_ignore`` (a list of object IDs) to
    remove undesired objects from the graph.

    Use ``highlight`` (a predicate) to highlight certain graph nodes in blue.

    Examples:

        >>> show_refs(obj)
        >>> show_refs([obj1, obj2])
        >>> show_refs(obj, max_depth=5)
        >>> show_refs(obj, filter=lambda x: not inspect.isclass(x))
        >>> show_refs(obj, highlight=inspect.isclass)
        >>> show_refs(obj, extra_ignore=[id(locals())])

    """
    show_graph(objs, max_depth=max_depth, extra_ignore=extra_ignore,
               filter=filter, too_many=too_many, highlight=highlight,
               edge_func=gc.get_referents, swap_source_target=True)

#
# Internal helpers
#

def show_graph(objs, edge_func, swap_source_target,
               max_depth=3, extra_ignore=(), filter=None, too_many=10,
               highlight=None):
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    f = file('objects.dot', 'w')
    print >> f, 'digraph ObjectGraph {'
    print >> f, '  node[shape=box, style=filled, fillcolor=white];'
    queue = []
    depth = {}
    ignore = set(extra_ignore)
    ignore.add(id(objs))
    ignore.add(id(extra_ignore))
    ignore.add(id(queue))
    ignore.add(id(depth))
    ignore.add(id(ignore))
    for obj in objs:
        print >> f, '  %s[fontcolor=red];' % (obj_node_id(obj))
        depth[id(obj)] = 0
        queue.append(obj)
    gc.collect()
    nodes = 0
    while queue:
        nodes += 1
        target = queue.pop(0)
        tdepth = depth[id(target)]
        print >> f, '  %s[label="%s"];' % (obj_node_id(target), obj_label(target, tdepth))
        h, s, v = gradient((0, 0, 1), (0, 0, .3), tdepth, max_depth)
        if inspect.ismodule(target):
            h = .3
            s = 1
        if highlight and highlight(target):
            h = .6
            s = .6
            v = 0.5 + v * 0.5
        print >> f, '  %s[fillcolor="%g,%g,%g"];' % (obj_node_id(target), h, s, v)
        if v < 0.5:
            print >> f, '  %s[fontcolor=white];' % (obj_node_id(target))
        if inspect.ismodule(target) or tdepth >= max_depth:
            continue
        neighbours = edge_func(target)
        ignore.add(id(neighbours))
        n = 0
        for source in neighbours:
            if inspect.isframe(source) or id(source) in ignore:
                continue
            if filter and not filter(source):
                continue
            if swap_source_target:
                srcnode, tgtnode = target, source
            else:
                srcnode, tgtnode = source, target
            elabel = edge_label(srcnode, tgtnode)
            print >> f, '  %s -> %s%s;' % (obj_node_id(srcnode), obj_node_id(tgtnode), elabel)
            if id(source) not in depth:
                depth[id(source)] = tdepth + 1
                queue.append(source)
            n += 1
            if n >= too_many:
                print >> f, '  %s[color=red];' % obj_node_id(target)
                break
    print >> f, "}"
    f.close()
    print "Graph written to objects.dot (%d nodes)" % nodes
    if os.system('which xdot >/dev/null') == 0:
        print "Spawning graph viewer (xdot)"
        os.system("xdot objects.dot &")
    else:
        os.system("dot -Tpng objects.dot > objects.png")
        print "Image generated as objects.png"


def obj_node_id(obj):
    if isinstance(obj, weakref.ref):
        return 'all_weakrefs_are_one'
    return ('o%d' % id(obj)).replace('-', '_')


def obj_label(obj, depth):
    return quote(type(obj).__name__ + ':\n' +
                 safe_repr(obj))


def quote(s):
    return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")


def safe_repr(obj):
    try:
        return short_repr(obj)
    except:
        return '(unrepresentable)'


def short_repr(obj):
    if isinstance(obj, (type, types.ModuleType, types.BuiltinMethodType,
                        types.BuiltinFunctionType)):
        return obj.__name__
    if isinstance(obj, types.MethodType):
        if obj.im_self is not None:
            return obj.im_func.__name__ + ' (bound)'
        else:
            return obj.im_func.__name__
    if isinstance(obj, (tuple, list, dict, set)):
        return '%d items' % len(obj)
    if isinstance(obj, weakref.ref):
        return 'all_weakrefs_are_one'
    return repr(obj)[:40]


def gradient(start_color, end_color, depth, max_depth):
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


def edge_label(source, target):
    if isinstance(target, dict) and target is getattr(source, '__dict__', None):
        return ' [label="__dict__",weight=10]'
    elif isinstance(source, dict):
        for k, v in source.iteritems():
            if v is target:
                if isinstance(k, basestring) and k:
                    return ' [label="%s",weight=2]' % quote(k)
                else:
                    return ' [label="%s"]' % quote(safe_repr(k))
    return ''

