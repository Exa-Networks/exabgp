# encoding: utf-8
"""
supervisor.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time
import signal
import select

from exabgp.version import version

from exabgp.structure.daemon import Daemon
from exabgp.structure.processes import Processes,ProcessError
from exabgp.structure.configuration import Configuration
from exabgp.bgp.peer import Peer
from exabgp.bgp.connection import errno_block

from exabgp.structure.log import Logger

class Supervisor (object):
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])

	def __init__ (self,configuration):
		self.logger = Logger()
		self.daemon = Daemon(self)
		self.processes = None
		self.configuration = Configuration(configuration)

		self._peers = {}
		self._shutdown = False
		self._reload = False
		self._restart = False
		self._route_update = False
		self._commands = {}
		self._saved_pid = False

		signal.signal(signal.SIGTERM, self.sigterm)
		signal.signal(signal.SIGHUP, self.sighup)
		signal.signal(signal.SIGALRM, self.sigalrm)

	def sigterm (self,signum, frame):
		self.logger.info("SIG TERM received",'supervisor')
		self._shutdown = True

	def sighup (self,signum, frame):
		self.logger.info("SIG HUP received",'supervisor')
		self._reload = True

	def sigalrm (self,signum, frame):
		self.logger.info("SIG ALRM received",'supervisor')
		self._restart = True

	def run (self,supervisor_speed=0.5):
		if self.daemon.drop_privileges():
			self.logger.error("Could not drop privileges to '%s' refusing to run as root" % self.daemon.user,'supervisor')
			self.logger.error("Set the environmemnt value exabgp.daemon.user to change the unprivileged user",'supervisor')
			return
		self.daemon.daemonise()
		if not self.daemon.savepid():
			self.logger.error('could not update PID, not starting','supervisor')

		# Make sure we create processes one we have dropped privileges and closed file descriptor
		self.processes = Processes(self)
		self.reload()

		# did we complete the run of updates caused by the last SIGHUP ?
		reload_completed = True

		while True:
			try:
				while self._peers:
					start = time.time()

					self.handle_commands(self.processes.received())

					if self._shutdown:
						self._shutdown = False
						self.shutdown()
					elif self._reload and reload_completed:
						self._reload = False
						self.reload()
					elif self._restart:
						self._restart = False
						self.restart()
					elif self._route_update:
						self._route_update = False
						self.route_update()
					elif self._commands:
						self.commands(self._commands)
						self._commands = {}

					reload_completed = True
					# Handle all connection
					peers = self._peers.keys()
					ios = []
					while peers:
						for key in peers[:]:
							peer = self._peers[key]
							# there was no routes to send for this peer, we performed keepalive checks
							if peer.run() is not True:
								# no need to come back to it before a a full cycle
								if peer.bgp and peer.bgp.connection:
									ios.append(peer.bgp.connection.io)
								peers.remove(key)
						# otherwise process as many routes as we can within a second for the remaining peers
						duration = time.time() - start
						# RFC state that we MUST not more than one KEEPALIVE / sec
						# And doing less could cause the session to drop
						if duration >= 1.0:
							reload_completed = False
							ios=[]
							break
					duration = time.time() - start
					if ios:
						try:
							read,_,_ = select.select(ios,[],[],max(supervisor_speed-duration,0))
						except select.error,e:
							errno,message = e.args
							if not errno in errno_block:
								raise
					else:
						if duration < supervisor_speed:
							time.sleep(max(supervisor_speed-duration,0))
				self.processes.terminate()
				self.daemon.removepid()
				break
			except KeyboardInterrupt:
				self.logger.info("^C received",'supervisor')
				self._shutdown = True
			except SystemExit:
				self.logger.info("exiting",'supervisor')
				self._shutdown = True
			except IOError:
				self.logger.warning("I/O Error received, most likely ^C during IO",'supervisor')
				self._shutdown = True
			except ProcessError:
				self.logger.error("Problem when sending message(s) to helper program, stopping",'supervisor')
				self._shutdown = True
#				from exabgp.leak import objgraph
#				print objgraph.show_most_common_types(limit=20)
#				import random
#				obj = objgraph.by_type('RouteBGP')[random.randint(0,2000)]
#				objgraph.show_backrefs([obj], max_depth=10)

	def shutdown (self):
		"""terminate all the current BGP connections"""
		self.logger.info("Performing shutdown",'supervisor')
		for key in self._peers.keys():
			self._peers[key].stop()

	def reload (self):
		"""reload the configuration and send to the peer the route which changed"""
		self.logger.info("Performing reload of exabgp %s" % version,'supervisor')

		reloaded = self.configuration.reload()
		if not reloaded:
			self.logger.error("Problem with the configuration file, no change done",'configuration')
			self.logger.error(self.configuration.error,'configuration')
			return

		for key, peer in self._peers.items():
			if key not in self.configuration.neighbor:
				self.logger.supervisor("Removing Peer %s" % peer.neighbor.name())
				peer.stop()

		for key, neighbor in self.configuration.neighbor.items():
			# new peer
			if key not in self._peers:
				self.logger.supervisor("New Peer %s" % neighbor.name())
				peer = Peer(neighbor,self)
				self._peers[key] = peer
			else:
				# check if the neighbor definition are the same (BUT NOT THE ROUTES)
				if self._peers[key].neighbor != neighbor:
					self.logger.supervisor("Peer definition change, restarting %s" % str(key))
					self._peers[key].restart(neighbor)
				# set the new neighbor with the new routes
				else:
					self.logger.supervisor("Updating routes for peer %s" % str(key))
					self._peers[key].reload(neighbor.every_routes())
		self.logger.warning("Loaded new configuration successfully",'configuration')
		# This only starts once ...
		self.processes.start()

	def handle_commands (self,commands):
		for service in commands:
			for command in commands[service]:
				# watchdog
				if command.startswith('announce watchdog') or command.startswith('withdraw watchdog'):
					parts = command.split(' ')
					try:
						name = parts[2]
					except IndexError:
						name = service
					if parts[0] == 'announce':
						for neighbor in self.configuration.neighbor:
							self.configuration.neighbor[neighbor].watchdog.announce(name)
					elif parts[0] == 'withdraw':
						for neighbor in self.configuration.neighbor:
							self.configuration.neighbor[neighbor].watchdog.withdraw(name)
					else:
						# should never happen
						pass
					self._route_update = True

				# route announcement / withdrawal
				elif command.startswith('announce route'):
					routes = self.configuration.parse_api_route(command)
					if not routes:
						self.logger.warning("Command could not parse route in : %s" % command,'supervisor')
					else:
						for route in routes:
							self.configuration.remove_route_all_peers(route)
							self.configuration.add_route_all_peers(route)
							self.logger.warning("Route added : %s" % route,'supervisor')
						self._route_update = True

				elif command.startswith('withdraw route'):
					routes = self.configuration.parse_api_route(command)
					if not routes:
						self.logger.warning("Command could not parse route in : %s" % command,'supervisor')
					else:
						for route in routes:
							if self.configuration.remove_route_all_peers(route):
								self.logger.supervisor("Route found : %s" % route)
							self._route_update = True
						if not self._route_update:
							self.logger.warning("Could not find route : %s" % route,'supervisor')

				# flow announcement / withdrawal
				elif command.startswith('announce flow'):
					flows = self.configuration.parse_api_flow(command)
					if not flows:
						self.logger.supervisor("Command could not parse flow in : %s" % command)
					else:
						for flow in flows:
							self.configuration.add_route_all_peers(flow)
						self._route_update = True

				elif command.startswith('withdraw flow'):
					flows = self.configuration.parse_api_flow(command)
					if not flows:
						self.logger.supervisor("Command could not parse flow in : %s" % command)
					else:
						for flow in flows:
							if self.configuration.remove_route_all_peers(flow):
								self.logger.supervisor("Command success, flow found and removed : %s" % flow)
								self._route_update = True
							if not self._route_update:
								self.logger.supervisor("Could not find flow : %s" % flow)

				# commands
				elif command in ['reload','restart','shutdown','version']:
					self._commands.setdefault(service,[]).append(command)

				elif command.startswith('show '):
					self._commands.setdefault(service,[]).append(command)

				# unknown
				else:
					self.logger.warning("Command from process not understood : %s" % command,'supervisor')

	def _answer (self,service,string):
		self.processes.write(service,string)
		self.logger.supervisor('Responding to %s : %s' % (service,string))

	def commands (self,commands):
		for service in commands:
			for command in commands[service]:
				if command == 'shutdown':
					self._shutdown = True
					self._answer(service,'shutdown in progress')
					continue
				if command == 'reload':
					self._reload = True
					self._answer(service,'reload in progress')
					continue
				if command == 'restart':
					self._restart = True
					self._answer(service,'restart in progress')
					continue
				if command == 'version':
					self._answer(service,'exabgp %s' % version)
					continue

				if command == 'show neighbors':
					self._answer(service,'This command holds ExaBGP, do not be surprised if it takes ages and then cause peers to drop ...\n')
					for key in self.configuration.neighbor.keys():
						neighbor = self.configuration.neighbor[key]
						for line in str(neighbor).split('\n'):
							self._answer(service,line)

				elif command == 'show routes':
					self._answer(service,'This command holds ExaBGP, do not be surprised if it takes ages and then cause peers to drop ...\n')
					for key in self.configuration.neighbor.keys():
						neighbor = self.configuration.neighbor[key]
						for route in neighbor.every_routes():
							self._answer(service,'neighbor %s %s' % (neighbor.local_address,route))

				elif command == 'show routes extensive':
					self._answer(service,'This command holds ExaBGP, do not be surprised if it takes ages and then cause peers to drop ...\n')
					for key in self.configuration.neighbor.keys():
						neighbor = self.configuration.neighbor[key]
						for route in neighbor.every_routes():
							self._answer(service,'neighbor %s %s' % (neighbor.name(),route.extensive()))

				else:
					self._answer(service,'unknown command %s' % command)

	def route_update (self):
		"""the process ran and we need to figure what routes to changes"""
		self.logger.supervisor("Performing dynamic route update")

		for key in self.configuration.neighbor.keys():
			neighbor = self.configuration.neighbor[key]
			self._peers[key].reload(neighbor.every_routes())
		self.logger.supervisor("Updated peers dynamic routes successfully")

	def restart (self):
		"""kill the BGP session and restart it"""
		self.logger.info("Performing restart of exabgp %s" % version,'supervisor')
		self.configuration.reload()

		for key in self._peers.keys():
			if key not in self.configuration.neighbor.keys():
				neighbor = self.configuration.neighbor[key]
				self.logger.supervisor("Removing Peer %s" % neighbor.name())
				self._peers[key].stop()
			else:
				self._peers[key].restart()
		self.processes.terminate()
		self.processes.start()

	def unschedule (self,peer):
		key = peer.neighbor.name()
		if key in self._peers:
			del self._peers[key]
