# encoding: utf-8
"""
line/reactor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.version import version as _version
from exabgp.reactor.api.command.command import Command


def register_reactor ():
	pass


@Command.register('text','help')
def manual (self, reactor, service, _):
	reactor.processes.answer(service,'command are:')
	for command in sorted(self.callback['text']):
		reactor.processes.answer(service,command)
	reactor.processes.answer_done(service)
	return True


@Command.register('text','shutdown')
def shutdown (self, reactor, service, _):
	reactor.signal.received = reactor.signal.SHUTDOWN
	reactor.processes.answer(service,'shutdown in progress')
	reactor.processes.answer_done(service)
	return True


@Command.register('text','reload')
def reload (self, reactor, service, _):
	reactor.signal.received = reactor.signal.RELOAD
	reactor.processes.answer(service,'reload in progress')
	reactor.processes.answer_done(service)
	return True


@Command.register('text','restart')
def restart (self, reactor, service, _):
	reactor.signal.received = reactor.signal.RESTART
	reactor.processes.answer(service,'restart in progress')
	reactor.processes.answer_done(service)
	return True


@Command.register('text','version')
def version (self, reactor, service, _):
	reactor.processes.answer(service,'exabgp %s' % _version,force=True)
	reactor.processes.answer_done(service)
	return True


@Command.register('text','#')
def comment (self, reactor, service, line):
	self.logger.processes(line.lstrip().lstrip('#').strip())
	reactor.processes.answer_done(service)
	return True


@Command.register('text','reset')
def reset (self, reactor, service, line):
	reactor.async.clear(service)
