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

from exabgp.structure.environment import environment
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
		self._saved_pid = False
		self._commands = []
		self._pending = []

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
						self.reload()
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
							# there was no routes to send for this peer, we performed keepalive checks
							if peer.run() is not True:
								if peer.bgp and peer.bgp.connection:
									ios.append(peer.bgp.connection.io)
								# no need to come back to it before a a full cycle
								peers.remove(key)

						duration = time.time() - start
						if duration >= 1.0:
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
						if duration >= 1.0:
							break

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
					self._peers[key].reload(neighbor)
		self.logger.warning("Loaded new configuration successfully",'configuration')
		# This only starts once ...
		self.processes.start()

	def run_pending (self,pending):
		# generators can return True or False, False mean they do not want more
		# generators to be return (route updates)
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


		def extract_peers (separator,command):
			restrict,command = command.split(separator)
			command = separator + command
			neighbor,peers = restrict.split(' ',1)
			peers = [_.strip() for _ in peers.split(',') if _]
			return command, peers


		# route announcement / withdrawal
		if 'announce route' in command:
			def _announce_route (self,command,peers):
				routes = self.configuration.parse_api_route(command)
				if not routes:
					self.logger.warning("Command could not parse route in : %s" % command,'supervisor')
					yield True
				else:
					for route in routes:
						self.configuration.remove_route_from_peers(route,peers)
						self.configuration.add_route_to_peers(route,peers)
						self.logger.warning("Route added : %s" % route,'supervisor')
						yield False
					self._route_update = True

			if command.startswith('announce route'):
				self._pending.append(_announce_route(self,command,None))
				return True
			if command.startswith('neighbor '):
				command,peers = extract_peers('announce',command)
				self._pending.append(_announce_route(self,command,peers))
				return True

		if 'withdraw route' in command:
			def _withdraw_route (self,command,peers):
				routes = self.configuration.parse_api_route(command)
				if not routes:
					self.logger.warning("Command could not parse route in : %s" % command,'supervisor')
					yield True
				else:
					for route in routes:
						if self.configuration.remove_route_from_peers(route,peers):
							self.logger.supervisor("Route found and removed : %s" % route)
							yield False
						else:
							self.logger.warning("Could not find therefore remove route : %s" % route,'supervisor')
							yield False
					self._route_update = True
			if command.startswith('withdraw route'):
				self._pending.append(_withdraw_route(self,command,None))
				return True
			if command.startswith('neighbor '):
				command,peers = extract_peers('withdraw',command)
				self._pending.append(_withdraw_route(self,command,peers))
				return True

		# flow announcement / withdrawal
		if 'announce flow' in command:
			def _announce_flow (self,command,peers):
				flows = self.configuration.parse_api_flow(command)
				if not flows:
					self.logger.supervisor("Command could not parse flow in : %s" % command)
					yield True
				else:
					for flow in flows:
						self.configuration.remove_route_from_peers(flow,peers)
						self.configuration.add_route_to_peers(flow,peers)
						self.logger.warning("Flow added : %s" % flow,'supervisor')
						yield False
					self._route_update = True
			if command.startswith('announce flow'):
				self._pending.append(_announce_flow(self,command,None))
				return True
			if command.startswith('neighbor '):
				command,peers = extract_peers('announce',command)
				self._pending.append(_announce_flow(self,command,peers))
				return True

		if 'withdraw flow' in command:
			def _withdraw_flow (self,command,peers):
				flows = self.configuration.parse_api_flow(command)
				if not flows:
					self.logger.supervisor("Command could not parse flow in : %s" % command)
					yield True
				else:
					for flow in flows:
						if self.configuration.remove_route_from_peers(flow,peers):
							self.logger.supervisor("Flow found and removed : %s" % flow)
							yield False
						else:
							self.logger.warning("Could not find therefore remove flow : %s" % flow,'supervisor')
							yield False
					self._route_update = True
			if command.startswith('withdraw flow'):
				self._pending.append(_withdraw_flow(self,command,None))
				return True
			if command.startswith('neighbor '):
				command,peers = extract_peers('withdraw',command)
				self._pending.append(_withdraw_flow(self,command,peers))
				return True

		# unknown
		self.logger.warning("Command from process not understood : %s" % command,'supervisor')
		return False

	def _answer (self,service,string):
		self.processes.write(service,string)
		self.logger.supervisor('Responding to %s : %s' % (service,string))


	def route_update (self):
		"""the process ran and we need to figure what routes to changes"""
		self.logger.supervisor("Performing dynamic route update")
		for key in self.configuration.neighbor.keys():
			neighbor = self.configuration.neighbor[key]
			self._peers[key].reload(neighbor)
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
