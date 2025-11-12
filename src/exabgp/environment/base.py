from __future__ import annotations

import os
import sys


def _find_root() -> str:
    app_folder: str = 'src/exabgp/application'
    root: str = os.environ.get('EXABGP_ROOT', '')

    if not root:
        root = os.path.dirname(sys.argv[0])
    root = os.path.normpath(os.path.abspath(root))

    if root.endswith('/bin') or root.endswith('/sbin'):
        root = os.path.normpath(os.path.join(root, '..'))

    _index = root.find(app_folder)
    if _index >= 0:
        root = root[:_index]

    if root.endswith('/'):
        root = root[:-1]

    return root


APPLICATION: str = 'exabgp'
ROOT: str = _find_root()
ETC: str = os.path.join(ROOT, 'etc', APPLICATION)
ENVFILE: str = os.path.join(ETC, f'{APPLICATION}.env')
