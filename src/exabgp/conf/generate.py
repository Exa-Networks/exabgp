#!/usr/bin/env python
# encoding: utf-8

import os
import astunparse

from exabgp.conf.yang import Tree 
from exabgp.conf.yang import Code


class Generate(object):
    intro = '# yang model structure and validation\n# autogenerate by exabgp\n\n'
    variable = '{name} = {data}\n'

    def __init__(self, fname):
        self.fname = fname
        self.dicts = []
        self.codes = []

    def add_dict(self, name, data):
        self.dicts.append((name, data))

    def add_code(self, block):
        self.codes.append(block)

    def _generate(self):
        returned = self.intro
        for name, data in self.dicts:
            returned += self.variable.format(name=name, data=data)
            returned += '\n'
        for section in self.codes:
            returned += section
            returned += '\n'
        return returned

    def save(self):
        print(f'generating {self.fname}')
        with open(self.fname, 'w') as w:
            w.write(self._generate())

    def output(self):
        # for name, data in self.dicts:
        #     pprint.pprint(name)
        #     pprint.pprint(data)
        for section in self.codes:
            print(section)


def main():
    folder = os.path.dirname(__file__)
    data = os.path.join(folder, '..', '..', '..', 'data')
    os.chdir(os.path.abspath(data))

    library = 'yang-library-data.json'
    module = 'exabgp'
    models = 'models'
    fname = '{module}-yang.py'

    gen = Generate(fname)

    tree = Tree(library, models, module).parse()

    gen.add_dict('model', tree)
    # gen.output()

    code = Code(tree)
    ast = code.generate(module)
    block = astunparse.unparse(ast)
    gen.add_code(block)

    gen.output()
    # # gen.save()


if __name__ == "__main__":
    main()
