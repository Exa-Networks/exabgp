# encoding: utf-8
"""
message.py

Created by Thomas Mangin on 2013-02-26.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


class Message (int):
	ROUTE_MONITORING = 0
	STATISTICS_REPORT = 1
	PEER_DOWN_NOTIFICATION = 2

	_str = {
		0: 'route monitoring',
		1: 'statistics report',
		2: 'peer down notification',
	}

	def __str__ (self):
		return self._str.get(self,'unknow %d' % self)

	def validate (self):
		return self in (0,1,2)

stat = {
	0: "prefixes rejected by inbound policy",
	1: "(known) duplicate prefix advertisements",
	2: "(known) duplicate withdraws",
	3: "updates invalidated due to CLUSTER_LIST loop",
	4: "updates invalidated due to AS_PATH loop",
}

peer = {
	1: "Local system closed session, notification sent",
	2: "Local system closed session, no notification",
	3: "Remote system closed session, notification sent",
	4: "Remote system closed session, no notification",
}
