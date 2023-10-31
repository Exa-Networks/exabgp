import os

# this is where the environment should be taken from
# it makes sure the environment is setup before it is imported

import exabgp.environment.setup  # noqa: F401,E261
from exabgp.environment.environment import Env  # noqa: F401,E261

from exabgp.environment.base import APPLICATION  # noqa: F401,E261
from exabgp.environment.base import ENVFILE  # noqa: F401,E261
from exabgp.environment.base import ROOT  # noqa: F401,E261
from exabgp.environment.base import ETC  # noqa: F401,E261

# As soon as we import anything, a COPY is made in the local
# namespace, it mean that we can not import the GlobalHashTable
# directly but must ask for a copy to be made each time
# at the time of import, so using a function get around it
from exabgp.environment.hashtable import GlobalHashTable as __


def getenv():
    return __()


def getconf(name):
    # some users are using symlinks for atomic change of the configuration file
    # using mv may however be better practice :p
    # so we must not follow symlink when looking for the file
    if name.startswith('etc/exabgp'):
        normalised = os.path.join(ETC, name[11:])
    else:
        normalised = os.path.normpath(name)

    absolute = os.path.abspath(normalised)
    if os.path.isfile(absolute):
        return absolute

    return ''
