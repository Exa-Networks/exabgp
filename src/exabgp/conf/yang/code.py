"""code.py

Created by Thomas Mangin on 2020-09-01.
Copyright (c) 2020 Exa Networks. All rights reserved.
"""

# Used https://github.com/asottile/astpretty
# to understand how the python AST works
# Python 3.9 will have ast.unparse but until then
# https://github.com/simonpercivall/astunparse
# is used to generate code from the AST created

from __future__ import annotations

from ast import Module, Import, FunctionDef, arguments, arg, alias
from ast import Load, Call, Return, Name, Attribute, Constant  # , Param
from ast import If, Compare, Gt, Lt, And  # , Add, GtE, LtE, Or
from ast import BoolOp, UnaryOp, Not, USub

# import astunparse

from exabgp.conf.yang.datatypes import kw
from exabgp.conf.yang.datatypes import ranges

import sys

if sys.version_info[:3] < (3, 7):

    def breakpoint():
        import pdb  # noqa: T100

        pdb.set_trace()  # noqa: T100
        pass  # noqa: PIE790


class Code:
    def __init__(self, tree):
        # the modules (import) required within the generated function
        self.imported = set()
        # type/function referenced in other types (union, ...)
        # which should therefore also be generated
        self.referenced = set()
        # the parsed yang as a tree
        self.tree = tree
        # the main yang namespace/module
        self.module = tree[kw['loaded']][0]
        # the namespace we are working in
        self.ns = self.module

    @staticmethod
    def _missing(**kargs):
        sys.stdout.write(' '.join(f'{k}={v}' for k, v in kargs.items()))
        sys.stdout.write('\n')
        # this code path was not handled
        breakpoint()

    @staticmethod
    def _unique(name, counter={}):  # noqa: B006 - intentional accumulator pattern
        unique = counter.get(name, 0)
        unique += 1
        counter[name] = unique
        return f'{name}_{unique}'

    @staticmethod
    def _return_boolean(value):
        return [
            Return(
                value=Constant(value=value, kind=None),
            ),
        ]

    def _python_name(self, name):
        if self.ns != self.tree[kw['loaded']][0] and ':' not in name:
            # XXX: could this lead to function shadowing?
            name = f'{self.ns}:{name}'
        # XXX: could this lead to function shadowing?
        return name.replace(':', '__').replace('-', '_')

    def _if_pattern(self, pattern):
        self.imported.add('re')
        # fix known ietf regex use
        pattern = pattern.replace('\\p{N}\\p{L}', '\\w')
        return [
            If(
                test=UnaryOp(
                    op=Not(),
                    operand=Call(
                        func=Attribute(
                            value=Name(id='re', ctx=Load()),
                            attr='match',
                            ctx=Load(),
                        ),
                        args=[
                            Constant(value=pattern, kind=None),
                            Name(id='value', ctx=Load()),
                            Attribute(
                                value=Name(id='re', ctx=Load()),
                                attr='UNICODE',
                                ctx=Load(),
                            ),
                        ],
                        keywords=[],
                    ),
                ),
                body=[
                    Return(
                        value=Constant(value=False, kind=None),
                    ),
                ],
                orelse=[],
            ),
        ]

    def _if_length(self, minimum, maximum):
        return [
            If(
                test=Compare(
                    left=Constant(value=int(minimum), kind=None),
                    ops=[
                        Gt(),
                        Gt(),
                    ],
                    comparators=[
                        Call(
                            func=Name(id='len', ctx=Load()),
                            args=[Name(id='value', ctx=Load())],
                            keywords=[],
                        ),
                        Constant(value=int(maximum), kind=None),
                    ],
                ),
                body=[
                    Return(
                        value=Constant(value=False, kind=None),
                    ),
                ],
                orelse=[],
            ),
        ]

    def _iter_if_string(self, node):
        for what, sub in node.items():
            if what == kw['pattern']:
                yield self._if_pattern(sub)
                continue

            if what == kw['match']:
                self._missing(if_type=what, node=node)
                continue

            if what == kw['length']:
                yield self._if_length(*sub)
                continue

            self._missing(if_type=what, node=node)

    @staticmethod
    def _if_digit():
        return [
            If(
                test=UnaryOp(
                    op=Not(),
                    operand=Call(
                        func=Attribute(
                            value=Name(id='value', ctx=Load()),
                            attr='isdigit',
                            ctx=Load(),
                        ),
                        args=[],
                        keywords=[],
                    ),
                ),
                body=[
                    Return(
                        value=Constant(value=False, kind=None),
                    ),
                ],
                orelse=[],
            ),
        ]

    @staticmethod
    def _if_lt(value):
        if value >= 0:
            comparators: list = [Constant(value=value, kind=None)]
        else:
            comparators = [
                UnaryOp(
                    op=USub(),
                    operand=Constant(value=abs(value), kind=None),
                ),
            ]

        return [
            If(
                test=Compare(
                    left=Call(
                        func=Name(id='int', ctx=Load()),
                        args=[Name(id='value', ctx=Load())],
                        keywords=[],
                    ),
                    ops=[Lt()],
                    comparators=comparators,
                ),
                body=[
                    Return(
                        value=Constant(value=False, kind=None),
                    ),
                ],
                orelse=[],
            ),
        ]

    @staticmethod
    def _if_gt(value):
        if value >= 0:
            comparators: list = [Constant(value=value, kind=None)]
        else:
            comparators = [
                UnaryOp(
                    op=USub(),
                    operand=Constant(value=abs(value), kind=None),
                ),
            ]
        return [
            If(
                test=Compare(
                    left=Call(
                        func=Name(id='int', ctx=Load()),
                        args=[Name(id='value', ctx=Load())],
                        keywords=[],
                    ),
                    ops=[Gt()],
                    comparators=comparators,
                ),
                body=[
                    Return(
                        value=Constant(value=False, kind=None),
                    ),
                ],
                orelse=[],
            ),
        ]

    def _if_range(self, minimum, maximum):
        return self._if_digit() + self._if_lt(minimum) + self._if_gt(maximum)

    def _union(self, node):
        values = []
        generated = []

        for union in node:
            for what, sub in union.items():
                if ':' in what:
                    if what in generated:
                        # only generate any imported function once
                        continue
                    generated.append(what)
                    name = what
                    yield self._type(what, name, sub)
                else:
                    # this is a build_in type (and my have been refined)
                    # therefore generate one function per type
                    name = self._unique(what)
                    yield self._function(name, self._type(what, what, sub))

                values.append(
                    UnaryOp(
                        op=Not(),
                        operand=Call(
                            func=Name(id=self._python_name(name), ctx=Load()),
                            args=[Name(id='value', ctx=Load())],
                            keywords=[],
                        ),
                    ),
                )

        yield [
            If(
                test=BoolOp(
                    op=And(),
                    values=values,
                ),
                body=[
                    Return(
                        value=Constant(value=False, kind=None),
                    ),
                ],
                orelse=[],
            ),
        ]

    def _imported(self):
        for imported in self.imported:
            yield Import(names=[alias(name=imported, asname=None)])

    def _type(self, what, name, node):
        if what == 'union':
            return list(self._union(node))

        if what in ('int8', 'int16', 'int16', 'int32', 'uint8', 'uint16', 'uint16', 'uint32'):
            # not dealing with refine
            minimum, maximum = ranges[what]
            return self._if_range(minimum, maximum)

        if what == 'string':
            return list(self._iter_if_string(node))

        if ':' in what:
            ns, name = what.split(':', 1)
            backup_ns, self.ns = self.ns, ns
            answer = list(self._typedef(ns, name))
            self.ns = backup_ns
            return answer

        self._missing(what=what, name=name, node=node)

    def _iter(self, node):
        for keyword, content in node.items():
            yield self._type(keyword, keyword, content)

    def _function(self, name, body):
        # XXX: could this lead to function shadowing?
        return [
            FunctionDef(
                name=self._python_name(name),
                args=arguments(
                    posonlyargs=[],
                    args=[arg(arg='value', annotation=None, type_comment=None)],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=body + self._return_boolean(True),
                decorator_list=[],
                returns=None,
                type_comment=None,
            ),
        ]

    def _typedef(self, module, only):
        td = self.tree[module][kw['typedef']]

        for name in td:
            if only and only != name:
                continue
            body = list(self._iter(td[name][kw['type']]))
            yield self._function(name, body)

    def _module(self, module, only=''):
        generated = list(self._typedef(module, only))
        # while self.referenced:
        #     module, check = self.referenced.pop(0)
        #     generated += list(self._typedef(module, check))
        return generated

    def generate(self, module):
        # this must be run first so that the imported module can be generated
        body = list(self._module(module))
        ast = Module(
            body=list(self._imported()) + body,
            type_ignores=[],
        )
        return ast
