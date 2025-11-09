
"""yang/parser.py

Created by Thomas Mangin on 2020-09-01.
Copyright (c) 2020 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import pprint

from pygments.token import Token
from yanglexer import yanglexer

from exabgp.conf.yang.model import Model
from exabgp.conf.yang.datatypes import kw
from exabgp.conf.yang.datatypes import words
from exabgp.conf.yang.datatypes import types

import sys

if sys.version_info[:3] < (3, 7):

    def breakpoint():
        import pdb  # noqa: T100

        pdb.set_trace()  # noqa: T100
        pass  # noqa: PIE790


DEBUG = True


class Tree:
    ignore = (Token.Text, Token.Comment.Singleline)

    @staticmethod
    def formated(string):
        returned = ''
        for line in string.strip().split('\n'):
            line = line.strip()

            if line.endswith('+'):
                line = line[:-1].strip()
            if line.startswith('+'):
                line = line[1:].strip()

            if line and line[0] == line[-1]:
                if line[0] in ('"', "'"):
                    line = line[1:-1]
            returned += line
        return returned

    def __init__(self, library, models, yang):
        self.model = Model(library, models, yang)
        # the yang file parsed tokens (configuration block according to the syntax)
        self.tokens = []
        # the name of the module being parsed
        self.module = ''
        # module can declare a "prefix" (nickname), which can be used to make the syntax shorter
        self.prefix = ''
        # the parsed yang tree
        # - at the root are the namespace (the module names) and within
        #   * a key for all the typedef
        #   * a key for all the grouping
        #   * a key for the root of the configuration
        # - a key [loaded] with a list of the module loaded (first is the one parsed)
        # the names of all the configuration sections
        self.tree = {}
        # the current namespace (module) we are parsing
        self.ns = {}
        # where the grouping for this section are stored
        self.grouping = {}
        # where the typedef for this section are stored
        self.typedef = {}
        # where the configuration parsed is stored
        self.root = {}
        self.load(yang)

    def tokenise(self, module, ismodel):
        lexer = yanglexer.YangLexer()
        tokens = lexer.get_tokens(self.model.load(module, ismodel))
        return [(t, n) for (t, n) in tokens if t not in self.ignore]

    def unexpected(self, string):
        pprint.pprint(f'unexpected data: {string}')
        for t in self.tokens[:15]:
            sys.stdout.write(f'{t}\n')
        breakpoint()
        pass  # noqa: PIE790

    def pop(self, what=None, expected=None):
        token, string = self.tokens[0]
        if what is not None and not str(token).startswith(str(what)):
            self.unexpected(string)
        if expected is not None and string.strip() != expected:
            self.unexpected(string)
        self.tokens.pop(0)
        return string

    def peek(self, position, ponctuation=None):
        token, string = self.tokens[position]
        # the self includes a last ' '
        if ponctuation and ponctuation != token:
            self.unexpected(string)
        return token, string.rstrip()

    def skip_keyword_block(self, name):
        count = 0
        while True:
            t, v = self.tokens.pop(0)
            if t != Token.Punctuation:
                continue
            if v.strip() == '{':
                count += 1
            if v.strip() == '}':
                count -= 1
            if not count:
                break

    def set_subtrees(self):
        """To make the core more redeable the tree[module] structure
        is presented as subtrees, this reset all the subtree
        for the current module
        """
        self.ns = self.tree[self.module]
        self.grouping = self.ns[kw['grouping']]
        self.typedef = self.ns[kw['typedef']]
        self.root = self.ns[kw['root']]

    def imports(self, module):
        """load, and if missing and defined download, a yang module

        module: the name of the yang module to find
        prefix: how it is called (prefix)
        """
        backup = (self.tokens, self.module, self.prefix)
        # XXX: should it be module ??
        self.load(module, ismodel=True)
        self.tokens, self.module, self.prefix = backup
        self.set_subtrees()

    def load(self, module, ismodel=False):
        """Add a new yang module/namespace to the tree
        this _function is used when initialising the
        root module, as it does not perform backups
        """
        self.tree.setdefault(kw['loaded'], []).append(module)
        self.tokens = self.tokenise(module, ismodel)
        self.module = module
        self.prefix = module
        self.tree[module] = {
            kw['typedef']: {},
            kw['grouping']: {},
            kw['root']: {},
        }
        self.set_subtrees()
        self.parse()

    def parse(self):
        self._parse([], self.root)
        return self.tree

    def _parse(self, inside, tree):
        while self.tokens:
            token, string = self.peek(0)

            if token == Token.Punctuation and string == '}':
                # it is clearer to pop it in the caller
                return

            self._parse_one(inside, tree, token, string)

    def _parse_one(self, inside, tree, token, string):
        if token == Token.Comment.Multiline:
            # ignore multiline comments
            self.pop(Token.Comment.Multiline)
            return

        if token == Token.Keyword.Namespace:
            self.pop(Token.Keyword.Namespace, 'module')
            self.pop(Token.Literal.String)
            self.pop(Token.Punctuation, '{')
            self._parse(inside, tree)
            self.pop(Token.Punctuation, '}')
            return

        if token != Token.Keyword or string not in words:
            if ':' not in string:
                self.unknown(string, '')
                return

        self.pop(Token.Keyword, string)
        name = self.formated(self.pop(Token.Literal.String))

        if string == 'prefix':
            self.prefix = name
            self.pop(Token.Punctuation, ';')
            return

        if string in ('namespace', 'organization', 'contact', 'yang-version'):
            self.pop(Token.Punctuation, ';')
            return

        if string in ('revision', 'extension'):
            self.skip_keyword_block(Token.Punctuation)
            return

        if string in ('range', 'length'):
            self.pop(Token.Punctuation, ';')
            tree[kw[string]] = [_ for _ in name.replace(' ', '').replace('..', ' ').split()]
            return

        if string == 'import':
            token, string = self.peek(0, Token.Punctuation)
            if string == ';':
                self.pop(Token.Punctuation, ';')
                self.imports(name)
            if string == '{':
                self.pop(Token.Punctuation, '{')
                self.pop(Token.Keyword, 'prefix')
                # prefix = self.formated(self.pop(Token.Literal.String))
                self.pop(Token.Punctuation, ';')
                self.pop(Token.Punctuation, '}')
                self.imports(name)
                return

        if string in ('description', 'reference'):
            self.pop(Token.Punctuation, ';')
            # XXX: not saved during debugging
            if DEBUG:
                return
            tree[kw[string]] = name
            return

        if string in ('pattern', 'value', 'default', 'mandatory'):
            self.pop(Token.Punctuation, ';')
            tree[kw[string]] = name
            return

        if string == 'key':
            self.pop(Token.Punctuation, ';')
            tree[kw[string]] = name.split()
            return

        if string == 'typedef':
            self.pop(Token.Punctuation, '{')
            sub = self.typedef.setdefault(name, {})
            self._parse(inside + [name], sub)
            self.pop(Token.Punctuation, '}')
            return

        if string == 'enum':
            option = self.pop(Token.Punctuation)
            if option == ';':
                tree.setdefault(kw[string], []).append(name)
                return
            if option == '{':
                sub = tree.setdefault(name, {})
                self._parse(inside + [name], sub)
                self.pop(Token.Punctuation, '}')
                return

        if string == 'type':
            # make sure the use module name and not prefix, as prefix is not global
            if ':' in name:
                module, typeref = name.split(':', 1)
                if module == self.prefix:
                    name = f'{self.module}:{typeref}'
                    module = self.module

                if module not in self.tree:
                    self.unexpected(f'referenced non-included module {name}')
            elif name not in types:
                name = f'{self.module}:{name}'

            option = self.pop(Token.Punctuation)
            if option == ';':
                if name in types:
                    tree.setdefault(kw[string], {name: {}})
                    return

                if ':' not in name:
                    # not dealing with refine
                    # breakpoint()
                    tree.setdefault(kw[string], {name: {}})
                    return

                tree.setdefault(kw[string], {name: {}})
                return

            if option == '{':
                if name == 'union':
                    sub = tree.setdefault(kw[string], {}).setdefault(name, [])
                    while True:
                        what, name = self.peek(0)
                        name = self.formated(name)
                        if name == 'type':
                            union_type = {}
                            self._parse_one(inside + [name], union_type, what, name)
                            sub.append(union_type[kw['type']])
                            continue
                        if name == '}':
                            self.pop(Token.Punctuation, '}')
                            break
                        self.unexpected(f'did not expect this in an union: {what}')
                    return

                if name == 'enumeration':
                    sub = tree.setdefault(kw[string], {}).setdefault(name, {})
                    self._parse(inside + [name], sub)
                    self.pop(Token.Punctuation, '}')
                    return

                if name in types:
                    sub = tree.setdefault(kw[string], {}).setdefault(name, {})
                    self._parse(inside + [name], sub)
                    self.pop(Token.Punctuation, '}')
                    return

                if ':' in name:
                    sub = tree.setdefault(kw[string], {}).setdefault(name, {})
                    self._parse(inside + [name], sub)
                    self.pop(Token.Punctuation, '}')
                    return

        if string == 'uses':
            if name not in self.grouping:
                self.unexpected(f'could not find grouping calle {name}')
            tree.update(self.grouping[name])
            option = self.pop(Token.Punctuation)
            if option == ';':
                return
            if option == '{':
                sub = tree.setdefault(name, {})
                self._parse(inside + [name], sub)
                self.pop(Token.Punctuation, '}')
                return

        if string == 'grouping':
            self.pop(Token.Punctuation, '{')
            sub = self.grouping.setdefault(name, {})
            self._parse(inside + [name], sub)
            self.pop(Token.Punctuation, '}')
            return

        if string in ('container', 'list', 'leaf', 'leaf-list'):
            self.pop(Token.Punctuation, '{')
            sub = tree.setdefault(name, {kw[string]: {}})
            self._parse(inside + [name], sub)
            self.pop(Token.Punctuation, '}')
            return

        if string == 'refine':
            self.pop(Token.Punctuation, '{')
            sub = tree.setdefault(name, {})
            self._parse(inside + [name], sub)
            self.pop(Token.Punctuation, '}')
            return

        self.unknown(string, name)

    def unknown(self, string, name):
        # catch unknown keyword so we can implement them
        pprint.pprint(self.ns)
        pprint.pprint('\n')
        pprint.pprint(string)
        pprint.pprint(name)
        pprint.pprint('\n')
        for t in self.tokens[:15]:
            pprint.pprint(t)
        breakpoint()
        # good luck!
        pass  # noqa: PIE790
