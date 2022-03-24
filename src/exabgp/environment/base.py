import os
import sys

APPLICATION = 'exabgp'

ROOT = os.environ.get('EXABGP_ROOT','')
if not ROOT:
    ROOT = os.path.normpath(os.path.dirname(sys.argv[0]))
if ROOT.endswith('/bin') or ROOT.endswith('/sbin'):
    ROOT = os.path.normpath(os.path.join(ROOT,'..'))
ETC = os.path.join(ROOT, 'etc', APPLICATION)
ENVFILE = os.path.join(ETC, f'{APPLICATION}.env')
