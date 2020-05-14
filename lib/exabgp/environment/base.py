import os
import sys

APPLICATION = 'exabgp'

ROOT = os.path.normpath(os.environ.get('EXABGP_ROOT', os.path.dirname(sys.argv[0])))
ETC = os.path.join(ROOT, 'etc', APPLICATION)
ENVFILE = os.path.join(ETC, f'{APPLICATION}.env')
