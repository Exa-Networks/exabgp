#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import astunparse

import pprint
from typing import Any

from exabgp.conf.yang import Parser  # type: ignore[attr-defined]
from exabgp.conf.yang import Code  # type: ignore[attr-defined]


class Generate:
    intro = '# yang model structure and validation\n# autogenerate by exabgp\n\n'
    variable = '{name} = {data}\n'

    def __init__(self, fname: str) -> None:
        self.fname = fname
        self.dicts: list[tuple[str, Any]] = []
        self.codes: list[str] = []

    def add_dict(self, name: str, data: Any) -> None:
        self.dicts.append((name, data))

    def add_code(self, block: str) -> None:
        self.codes.append(block)

    def _generate(self) -> str:
        returned = self.intro
        for name, data in self.dicts:
            # NOTE: Do not convert to f-string! This uses a template pattern from self.variable
            # which is defined as a class attribute and allows customization.
            returned += self.variable.format(name=name, data=data)
            returned += '\n'
        for section in self.codes:
            returned += section
            returned += '\n'
        return returned

    def save(self) -> None:
        sys.stdout.write(f'generating {self.fname}\n')
        with open(self.fname, 'w') as w:
            w.write(self._generate())

    def output(self) -> None:
        for name, data in self.dicts:
            pprint.pprint(name)
            pprint.pprint(data)
        for section in self.codes:
            sys.stdout.write(f'{section}\n')


def main() -> None:
    folder = os.path.abspath(os.path.dirname(__file__))
    data = os.path.join(folder, '..', '..', '..', '..', 'data')
    os.chdir(os.path.abspath(data))

    library = 'yang-library-data.json'
    module = 'exabgp'
    models = 'models'
    fname = 'cache.py'

    gen = Generate(fname)

    tree = Parser(library, models, module).parse()

    gen.add_dict('model', tree)

    code = Code(tree)
    ast = code.generate(module)
    block = astunparse.unparse(ast)
    gen.add_code(block)

    os.chdir(folder)
    # gen.output()
    gen.save()


if __name__ == '__main__':
    main()
