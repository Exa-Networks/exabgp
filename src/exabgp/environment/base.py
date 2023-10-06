import os
import sys

def _find_root():
    app_folder = 'src/exabgp/application'
    root = os.environ.get('EXABGP_ROOT', '')

    if not root:
        root = os.path.dirname(sys.argv[0])
    root = os.path.normpath(os.path.abspath((root)))

    if root.endswith('/bin') or root.endswith('/sbin'):
        root = os.path.normpath(os.path.join(root, '..'))

    _index = root.find(app_folder)
    if _index >= 0:
        root = root[:_index]

    if root.endswith('/'):
        root = root[:-1]

    return root


APPLICATION = 'exabgp'
ROOT = _find_root()
ETC = os.path.join(ROOT, 'etc', APPLICATION)
ENVFILE = os.path.join(ETC, f'{APPLICATION}.env')



