# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# ================================================================== BGP States
#

class STATE (object):
	IDLE        = 0x01
	ACTIVE      = 0x02
	CONNECT     = 0x04
	OPENSENT    = 0x08
	OPENCONFIRM = 0x10
	ESTABLISHED = 0x20


# =================================================================== Direction
#

class OUT (object):
	ANNOUNCE = 0x01
	WITHDRAW = 0x02


class IN (object):
	ANNOUNCED = 0x01
	WITHDRAWN = 0x02


# ================================================================ Registration
#

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import Notification
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.operational import Operational

Message.register_message(Open)
Message.register_message(Update)
Message.register_message(KeepAlive)
Message.register_message(Notification)
Message.register_message(RouteRefresh)
Message.register_message(Operational)

from exabgp.bgp.message.notification import Notify

Message.klass_notify = Notify
