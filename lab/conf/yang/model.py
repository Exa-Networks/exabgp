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
from typing import Any


class Model:
    namespaces = {
        'ietf': 'https://raw.githubusercontent.com/YangModels/yang/master/standard/ietf/RFC',
    }

    models: dict[str, Any] = {}

    def __init__(self, library: str, folder: str, module: str) -> None:
        self.library = library
        self.folder = folder

        models = json.loads(open(self.library).read())

        for m in models['ietf-yang-library:modules-state']['module']:
            self.models[m['name']] = m

        if not os.path.exists('models'):
            os.mkdir('models')

    def _write(self, string: str) -> None:
        if not string.startswith('\n'):
            fill = ' ' * shutil.get_terminal_size().columns
            sys.stdout.write(f'\r{fill}\r')
        sys.stdout.write(string)
        sys.stdout.flush()

    # @classmethod
    # def fetch_models(self, folder):
    #     sys.stdout.write('downloading models\n')
    #     for module in self.models:
    #         self.fetch_model(folder, module)

    #     sys.stdout.write('done.\n\n')
    def load(self, module: str, infolder: bool = False) -> str:
        fname = f'{module}.yang'
        if infolder:
            fname = os.path.join(self.folder, fname)

        if not os.path.exists(fname):
            self.fetch(module)

        return open(fname).read()

    def fetch(self, module: str) -> None:
        if module not in self.models:
            sys.exit(f'{module} imported but not defined in yang-library-data.json')

        model = self.models[module]

        revision = model['revision']
        yang = f'{model}@{revision}.yang'
        save = f'{self.models}/{model}.yang'

        if 'schema' in model:
            url = model['schema']

        elif 'namespace' in model:
            namespace = model['namespace'].split(':')
            site = self.namespaces.get(namespace[1], '')
            if not site:
                raise RuntimeError('unimplemented namespace case')

            url = f'{site}/{yang}'
        else:
            raise RuntimeError('unimplemented yang-library case')

        if os.path.exists(save):
            self._write(f'👌 skipping {model} (already downloaded)')
            if self._verify(str(model), save):
                self._write('\n')
                return

        self._write(f'👁️  retrieve {model}@{revision} ({url})')

        try:
            urllib.request.urlretrieve(url, save)
            # indirect = urllib.request.urlopen(schema).read()
        except urllib.error.HTTPError as exc:
            self._write(f'\n🥺 failure attempting to retrieve {url}\n{exc}')
            return

        if not self._verify(str(model), save):
            sys.exit(f'\ninvalid yang content for {model}@{revision}')

        self._write(f'👍 retrieve {model}@{revision}\n')

    def _verify(self, name: str, save: str) -> bool:
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

    def clean_models(self) -> None:
        sys.stdout.write(f'cleaning {self.folder}\n')
        for file in glob.glob(f'{self.folder}/*.yang'):
            sys.stdout.write(f'cleanup: {file}\n')
            os.remove(file)
        sys.stdout.write('done.\n\n')
