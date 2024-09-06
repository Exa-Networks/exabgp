# Every MVPN should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN

from exabgp.bgp.message.update.nlri.mvpn.sourcead import SourceAD
from exabgp.bgp.message.update.nlri.mvpn.sourcejoin import SourceJoin
from exabgp.bgp.message.update.nlri.mvpn.sharedjoin import SharedJoin
