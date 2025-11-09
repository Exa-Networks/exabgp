
"""yang/model.py

Created by Thomas Mangin on 2020-09-01.
Copyright (c) 2020 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import os
import sys
import json
import glob
import shutil
import urllib
import urllib.request


class Model:
    namespaces = {
        'ietf': 'https://raw.githubusercontent.com/YangModels/yang/master/standard/ietf/RFC',
    }

    models = {}

    def __init__(self, library, folder, module):
        self.library = library
        self.folder = folder

        models = json.loads(open(self.library).read())

        for m in models['ietf-yang-library:modules-state']['module']:
            self.models[m['name']] = m

        if not os.path.exists('models'):
            os.mkdir('models')

    def _write(self, string):
        if not string.startswith('\n'):
            fill = ' ' * shutil.get_terminal_size().columns
            sys.stdout.write(f'\r{fill}\r')
        sys.stdout.write(string)
        sys.stdout.flush()

    # @classmethod
    # def fetch_models(self, folder):
    #     print('downloading models')

    #     for module in self.models:
    #         self.fetch_model(folder, module)

    #     print('done.\n')

    def load(self, module, infolder=False):
        fname = f'{module}.yang'
        if infolder:
            fname = os.path.join(self.folder, fname)

        if not os.path.exists(fname):
            self.fetch(module)

        return open(fname).read()

    def fetch(self, module):
        if module not in self.models:
            sys.exit(f'{module} imported but not defined in yang-library-data.json')

        module = self.models[module]

        revision = module['revision']
        yang = f'{module}@{revision}.yang'
        save = f'{self.models}/{module}.yang'

        if 'schema' in module:
            url = module['schema']

        elif 'namespace' in module:
            namespace = module['namespace'].split(':')
            site = self.namespaces.get(namespace[1], '')
            if not site:
                raise RuntimeError('unimplemented namespace case')

            url = f'{site}/{yang}'
        else:
            raise RuntimeError('unimplemented yang-library case')

        if os.path.exists(save):
            self._write(f'👌 skipping {module} (already downloaded)')
            if self._verify(module, save):
                self._write('\n')
                return

        self._write(f'👁️  retrieve {module}@{revision} ({url})')

        try:
            urllib.request.urlretrieve(url, save)
            # indirect = urllib.request.urlopen(schema).read()
        except urllib.error.HTTPError as exc:
            self._write(f'\n🥺 failure attempting to retrieve {url}\n{exc}')
            return

        if not self._verify(module, save):
            sys.exit(f'\ninvalid yang content for {module}@{revision}')

        self._write(f'👍 retrieve {module}@{revision}\n')

    def _verify(self, name, save):
        # simple but should be enough
        self._write(f'🔍 checking {name} for correct yaml')
        if not open(save).readline().startswith('module'):
            self._write(f'🥵 not-yang {name} does not contain a yang module')
            return False

        # XXX: removed tests - check later
        return True

        self._write(f'🔍 checking {name} for correct yaml')
        if not open(save).readline().startswith('module'):
            self._write(f'🥵 not-yang {name} does not contain a yang module')
            return False
        return True

    def clean_models(self):
        print(f'cleaning {self.folder}')
        for file in glob.glob(f'{self.folder}/*.yang'):
            print(f'cleanup: {file}')
            os.remove(file)
        print('done.\n')
