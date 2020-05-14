# this is where the environment should be taken from
# it makes sure the environment is setup before it is imported
import exabgp.environment.setup

from exabgp.environment.environment import Env

from exabgp.environment.base import APPLICATION
from exabgp.environment.base import ENVFILE
from exabgp.environment.base import ROOT
from exabgp.environment.base import ETC

# As soon as we import anything, a COPY is made in the local
# namespace, it mean that we can not import the GlobalHashTable
# directly but must ask for a copy to be made each time
# at the time of import, so using a function get around it
from exabgp.environment.hashtable import GlobalHashTable as __


def getenv():
    return __()
