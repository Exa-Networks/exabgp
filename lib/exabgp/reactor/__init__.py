# encoding: utf-8
"""
reactor.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import time
import signal
import select

from exabgp.version import version

from exabgp.util.errstr import errstr
from exabgp.reactor.daemon import Daemon
from exabgp.reactor.listener import Listener,NetworkError
from exabgp.reactor.api.processes import Processes,ProcessError
from exabgp.bgp.peer import Peer
from exabgp.reactor.network.error import error

from exabgp.configuration.file import Configuration
from exabgp.configuration.environment import environment

from exabgp.logger import Logger

class Reactor (object):
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])
	reactor_speed = 1.0

	def __init__ (self,configuration):
		self.logger = Logger()
		self.daemon = Daemon(self)
		self.processes = None
		self.listener = None
		self.configuration = Configuration(configuration)

		self._peers = {}
		self._shutdown = False
		self._reload = False
		self._reload_processes = False
		self._restart = False
		self._route_update = False
		self._saved_pid = False
		self._commands = []
		self._pending = []

		signal.signal(signal.SIGTERM, self.sigterm)
		signal.signal(signal.SIGHUP, self.sighup)
		signal.signal(signal.SIGALRM, self.sigalrm)
		signal.signal(signal.SIGUSR1, self.sigusr1)
		signal.signal(signal.SIGUSR2, self.sigusr2)

	def sigterm (self,signum, frame):
		self.logger.info("SIG TERM received - shutdown",'reactor')
		self._shutdown = True

	def sighup (self,signum, frame):
		self.logger.info("SIG HUP received - shutdown",'reactor')
		self._shutdown = True

	def sigalrm (self,signum, frame):
		self.logger.info("SIG ALRM received - restart",'reactor')
		self._restart = True

	def sigusr1 (self,signum, frame):
		self.logger.info("SIG USR1 received - reload configuration",'reactor')
		self._reload = True

	def sigusr2 (self,signum, frame):
		self.logger.info("SIG USR2 received - reload configuration and processes",'reactor')
		self._reload = True
		self._reload_processes = True

	def run (self):
		if environment.settings().tcp.bind:
			ip = environment.settings().tcp.bind
			port = environment.settings().tcp.port

			try:
				self.listener = Listener([ip,],port)
				self.listener.start()
			except NetworkError,e:
				self.listener = None
				if os.geteuid() != 0:
					self.logger.critical("You most likely need to run ExaBGP as root to bind to port 179",'reactor')
				else:
					self.logger.critical("Can not bind to %s:%d (%s)" % (ip,port,errstr(e)),'reactor')
				self.logger.critical("ExaBGP will not accept incoming connections",'reactor')
			self.logger.critical("Listening on %s:179" % ip,'reactor')

		if self.daemon.drop_privileges():
			self.logger.critical("Could not drop privileges to '%s' refusing to run as root" % self.daemon.user,'reactor')
			self.logger.critical("Set the environmemnt value exabgp.daemon.user to change the unprivileged user",'reactor')
			return

		self.daemon.daemonise()

		if not self.daemon.savepid():
			self.logger.error('could not update PID, not starting','reactor')

		# Make sure we create processes one we have dropped privileges and closed file descriptor
		self.processes = Processes(self)
		self.reload()

		# did we complete the run of updates caused by the last SIGUSR1/SIGUSR2 ?
		reload_completed = True

		wait = environment.settings().tcp.delay
		if wait:
			sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
			self.logger.error("waiting for %d seconds before connecting" % sleeptime)
			time.sleep(float(sleeptime))

		while True:
			try:
				while self._peers:
					start = time.time()

					if self._shutdown:
						self._shutdown = False
						self.shutdown()
					elif self._reload and reload_completed:
						self._reload = False
						self.reload(self._reload_processes)
						self._reload_processes = False
					elif self._restart:
						self._restart = False
						self.restart()
					elif self._route_update:
						self._route_update = False
						self.route_update()

					while self.schedule(self.processes.received()) or self._pending:
						self._pending = list(self.run_pending(self._pending))

						duration = time.time() - start
						if duration >= 0.5:
							break

					reload_completed = True
					# Handle all connection
					peers = self._peers.keys()
					ios = []
					while peers:
						for key in peers[:]:
							peer = self._peers[key]
							# peer.run returns:
							# * True if it wants to be called again
							# * None if it should be called again but has no work atm
							# * False if it is finished and is closing down, or restarting
							if peer.run() is not True:
								ios.extend(peer.ios())
								# no need to come back to it before a a full cycle
								peers.remove(key)

						duration = time.time() - start
						if duration >= self.reactor_speed:
							reload_completed = False
							ios=[]
							break

					# append here after reading as if read fails due to a dead process
					# we may respawn the process which changes the FD
					ios.extend(self.processes.fds())

					# RFC state that we MUST not send more than one KEEPALIVE / sec
					# And doing less could cause the session to drop

					while self.schedule(self.processes.received()) or self._pending:
						self._pending = list(self.run_pending(self._pending))

						duration = time.time() - start
						if duration >= self.reactor_speed:
							break

					if self.listener:
						for connection in self.listener.connected():
							found = False
							for key, neighbor in self.configuration.neighbor.items():
								# XXX: FIXME: Inet can only be compared to Inet
								if connection.local == str(neighbor.local_address) and connection.peer == str(neighbor.peer_address):
									self._peers[key].incoming(connection)
									found = True
									break
							if not found:
								connection.notification(2,2,'peer not configured')
								connection.close()

					if ios:
						duration = time.time() - start
						if duration < self.reactor_speed:
							try:
								read,_,_ = select.select(ios,[],[],max(self.reactor_speed-duration,0))
							except select.error,e:
								errno,message = e.args
								if not errno in error.block:
									raise e
					else:
						duration = time.time() - start
						if duration < self.reactor_speed:
							time.sleep(max(self.reactor_speed-duration,0))

				self.processes.terminate()
				self.daemon.removepid()
				break
			except KeyboardInterrupt:
				while True:
					try:
						self._shutdown = True
						self.logger.info("^C received",'reactor')
						break
					except KeyboardInterrupt:
						pass
			except SystemExit:
				while True:
					try:
						self._shutdown = True
						self.logger.info("exiting",'reactor')
						break
					except KeyboardInterrupt:
						pass
			except IOError:
				while True:
					try:
						self._shutdown = True
						self.logger.warning("I/O Error received, most likely ^C during IO",'reactor')
						break
					except KeyboardInterrupt:
						pass
			except ProcessError:
				while True:
					try:
						self._shutdown = True
						self.logger.error("Problem when sending message(s) to helper program, stopping",'reactor')
						break
					except KeyboardInterrupt:
						pass
			except select.error,e:
				while True:
					try:
						self._shutdown = True
						self.logger.error("problem using select, stopping",'reactor')
						break
					except KeyboardInterrupt:
						pass
#				from exabgp.leak import objgraph
#				print objgraph.show_most_common_types(limit=20)
#				import random
#				obj = objgraph.by_type('RouteBGP')[random.randint(0,2000)]
#				objgraph.show_backrefs([obj], max_depth=10)

	def shutdown (self):
		"""terminate all the current BGP connections"""
		self.logger.info("Performing shutdown",'reactor')
		if self.listener:
			self.listener.stop()
		for key in self._peers.keys():
			self._peers[key].stop()

	def reload (self,restart=False):
		"""reload the configuration and send to the peer the route which changed"""
		self.logger.info("Performing reload of exabgp %s" % version,'reactor')

		reloaded = self.configuration.reload()
		if not reloaded:
			self.logger.error("Problem with the configuration file, no change done",'configuration')
			self.logger.error(self.configuration.error,'configuration')
			return

		for key, peer in self._peers.items():
			if key not in self.configuration.neighbor:
				self.logger.reactor("Removing Peer %s" % peer.neighbor.name())
				peer.stop()

		for key, neighbor in self.configuration.neighbor.items():
			# new peer
			if key not in self._peers:
				self.logger.reactor("New Peer %s" % neighbor.name())
				peer = Peer(neighbor,self)
				self._peers[key] = peer
			else:
				# check if the neighbor definition are the same (BUT NOT THE ROUTES)
				if self._peers[key].neighbor != neighbor:
					self.logger.reactor("Peer definition change, restarting %s" % str(key))
					self._peers[key].restart(neighbor)
				# set the new neighbor with the new routes
				else:
					self.logger.reactor("Updating routes for peer %s" % str(key))
					self._peers[key].reload(neighbor)
		self.logger.warning("Loaded new configuration successfully",'configuration')
		# This only starts once ...
		self.processes.start(restart)

	def run_pending (self,pending):
		more = True
		for generator in pending:
			try:
				if more:
					more = generator.next()
				yield generator
			except StopIteration:
				pass

	def schedule (self,commands):
		self._commands.extend(commands)

		if not self._commands:
			return False

		service,command = self._commands.pop(0)

		if command == 'shutdown':
			self._shutdown = True
			self._pending = []
			self._commands = []
			self._answer(service,'shutdown in progress')
			return True

		if command == 'reload':
			self._reload = True
			self._pending = []
			self._commands = []
			self._answer(service,'reload in progress')
			return True

		if command == 'restart':
			self._restart = True
			self._pending = []
			self._commands = []
			self._answer(service,'restart in progress')
			return True

		if command == 'version':
			self._answer(service,'exabgp %s' % version)
			return True

		if command == 'show neighbors':
			def _show_neighbor (self):
				for key in self.configuration.neighbor.keys():
					neighbor = self.configuration.neighbor[key]
					for line in str(neighbor).split('\n'):
						self._answer(service,line)
						yield True
			self._pending.append(_show_neighbor(self))
			return True

		if command == 'show routes':
			def _show_route (self):
				for key in self.configuration.neighbor.keys():
					neighbor = self.configuration.neighbor[key]
					for route in list(neighbor.every_routes()):
						self._answer(service,'neighbor %s %s' % (neighbor.local_address,route))
						yield True
			self._pending.append(_show_route(self))
			return True

		if command == 'show routes extensive':
			def _show_extensive (self):
				for key in self.configuration.neighbor.keys():
					neighbor = self.configuration.neighbor[key]
					for route in list(neighbor.every_routes()):
						self._answer(service,'neighbor %s %s' % (neighbor.name(),route.extensive()))
						yield True
			self._pending.append(_show_extensive(self))
			return True

		# watchdog
		if command.startswith('announce watchdog'):
			def _announce_watchdog (self,name):
				for neighbor in self.configuration.neighbor:
					self.configuration.neighbor[neighbor].watchdog.announce(name)
					yield False
				self._route_update = True
			try:
				name = command.split(' ')[2]
			except IndexError:
				name = service
			self._pending.append(_announce_watchdog(self,name))
			return True

		# watchdog
		if command.startswith('withdraw watchdog'):
			def _withdraw_watchdog (self,name):
				for neighbor in self.configuration.neighbor:
					self.configuration.neighbor[neighbor].watchdog.withdraw(name)
					yield False
				self._route_update = True
			try:
				name = command.split(' ')[2]
			except IndexError:
				name = service
			self._pending.append(_withdraw_watchdog(self,name))
			return True

		def extract_neighbors (command):
			"""return a list of neighbor definition : the neighbor definition is a list of string which are in the neighbor indexing string"""
			returned = []
			definition = []
			neighbor,remaining = command.split(' ',1)
			if neighbor != 'neighbor':
				return [],command

			ip,command = remaining.split(' ',1)
			definition.append('%s %s' % (neighbor,ip))

			while True:
				try:
					key,value,remaining = command.split(' ',2)
				except ValueError:
					key,value = command.split(' ',1)
				if key == ',':
					returned.apppend(definition)
					_,command = command.split(' ',1)
					continue
				if key not in ['local-ip','local-as','peer-as','router-id','family-allowed']:
					if definition:
						returned.append(definition)
					break
				definition.append('%s %s' % (key,value))
				command = remaining

			return returned,command

		def match_neighbor (description,name):
			for string in description:
				if not string in name:
					return False
			return True

		def match_neighbors (description,peers):
			"returns the sublist of peers matching the description passed, or None if no description is given"
			if not description:
				return None

			returned = []
			for key in peers:
				for description in descriptions:
					if match_neighbor(description,key):
						returned.append(key)
			return returned

		# route announcement / withdrawal
		if 'announce route' in command:
			def _announce_route (self,command,peers):
				routes = self.configuration.parse_api_route(command)
				if not routes:
					self.logger.warning("Command could not parse route in : %s" % command,'reactor')
					yield True
				else:
					for route in routes:
						self.configuration.remove_route_from_peers(route,peers)
						self.configuration.add_route_to_peers(route,peers)
						self.logger.warning("Route added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',route),'reactor')
						yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				self._pending.append(_announce_route(self,command,peers))
				if peers == []:
					self.logger.warning('no neighbor matching the command : %s' % command,'reactor')
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		if 'withdraw route' in command:
			def _withdraw_route (self,command,peers):
				routes = self.configuration.parse_api_route(command)
				if not routes:
					self.logger.warning("Command could not parse route in : %s" % command,'reactor')
					yield True
				else:
					for route in routes:
						if self.configuration.remove_route_from_peers(route,peers):
							self.logger.reactor("Route found and removed : %s" % route)
							yield False
						else:
							self.logger.warning("Could not find therefore remove route : %s" % route,'reactor')
							yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				self._pending.append(_withdraw_route(self,command,peers))
				if peers == []:
					self.logger.warning('no neighbor matching the command : %s' % command,'reactor')
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		# flow announcement / withdrawal
		if 'announce flow' in command:
			def _announce_flow (self,command,peers):
				flows = self.configuration.parse_api_flow(command)
				if not flows:
					self.logger.reactor("Command could not parse flow in : %s" % command)
					yield True
				else:
					for flow in flows:
						self.configuration.remove_route_from_peers(flow,peers)
						self.configuration.add_route_to_peers(flow,peers)
						self.logger.warning("Flow added : %s" % flow,'reactor')
						yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				self._pending.append(_announce_flow(self,command,peers))
				if peers == []:
					self.logger.warning('no neighbor matching the command : %s' % command,'reactor')
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		if 'withdraw flow' in command:
			def _withdraw_flow (self,command,peers):
				flows = self.configuration.parse_api_flow(command)
				if not flows:
					self.logger.reactor("Command could not parse flow in : %s" % command)
					yield True
				else:
					for flow in flows:
						if self.configuration.remove_route_from_peers(flow,peers):
							self.logger.reactor("Flow found and removed : %s" % flow)
							yield False
						else:
							self.logger.warning("Could not find therefore remove flow : %s" % flow,'reactor')
							yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				self._pending.append(_withdraw_flow(self,command,peers))
				if peers == []:
					self.logger.warning('no neighbor matching the command : %s' % command,'reactor')
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		# route announcement / withdrawal
		if 'teardown' in command:
			try:
				descriptions,command = extract_neighbors(command)
				_,code = command.split(' ',1)
				for key in self._peers:
					for description in descriptions:
						if match_neighbor(description,key):
							self._peers[key].teardown(int(code))
							self.logger.warning('teardown scheduled for %s' % ' '.join(description),'reactor')
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		# unknown
		self.logger.warning("Command from process not understood : %s" % command,'reactor')
		return False

	def _answer (self,service,string):
		self.processes.write(service,string)
		self.logger.reactor('Responding to %s : %s' % (service,string))


	def route_update (self):
		"""the process ran and we need to figure what routes to changes"""
		self.logger.reactor("Performing dynamic route update")
		for key in self.configuration.neighbor.keys():
			neighbor = self.configuration.neighbor[key]
			self._peers[key].reload(neighbor)
		self.logger.reactor("Updated peers dynamic routes successfully")

	def restart (self):
		"""kill the BGP session and restart it"""
		self.logger.info("Performing restart of exabgp %s" % version,'reactor')
		self.configuration.reload()

		for key in self._peers.keys():
			if key not in self.configuration.neighbor.keys():
				neighbor = self.configuration.neighbor[key]
				self.logger.reactor("Removing Peer %s" % neighbor.name())
				self._peers[key].stop()
			else:
				self._peers[key].restart()
		self.processes.terminate()
		self.processes.start()

	def unschedule (self,peer):
		key = peer.neighbor.name()
		if key in self._peers:
			del self._peers[key]


