# encoding: utf-8
"""
reactor.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import re
import sys
import time
import signal
import select

from exabgp.version import version

from exabgp.reactor.daemon import Daemon
from exabgp.reactor.listener import Listener,NetworkError
from exabgp.reactor.api.processes import Processes,ProcessError
from exabgp.reactor.peer import Peer,ACTION
from exabgp.reactor.network.error import error

from exabgp.configuration.file import Configuration
from exabgp.configuration.environment import environment

from exabgp.logger import Logger

class Reactor (object):
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])

	def __init__ (self,configuration):
		self.ip = environment.settings().tcp.bind
		self.port = environment.settings().tcp.port

		self.max_loop_time = environment.settings().reactor.speed

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
		self.logger.reactor("SIG TERM received - shutdown")
		self._shutdown = True

	def sighup (self,signum, frame):
		self.logger.reactor("SIG HUP received - shutdown")
		self._shutdown = True

	def sigalrm (self,signum, frame):
		self.logger.reactor("SIG ALRM received - restart")
		self._restart = True

	def sigusr1 (self,signum, frame):
		self.logger.reactor("SIG USR1 received - reload configuration")
		self._reload = True

	def sigusr2 (self,signum, frame):
		self.logger.reactor("SIG USR2 received - reload configuration and processes")
		self._reload = True
		self._reload_processes = True

	def run (self):
		if self.ip:
			try:
				self.listener = Listener([self.ip,],self.port)
				self.listener.start()
			except NetworkError,e:
				self.listener = None
				if os.geteuid() != 0 and self.port <= 1024:
					self.logger.reactor("Can not bind to %s:%d, you may need to run ExaBGP as root" % (self.ip,self.port),'critical')
				else:
					self.logger.reactor("Can not bind to %s:%d (%s)" % (self.ip,self.port,str(e)),'critical')
				self.logger.reactor("unset exabgp.tcp.bind if you do not want listen for incoming connections",'critical')
				self.logger.reactor("and check that no other daemon is already binding to port %d" % self.port,'critical')
				sys.exit(1)
			self.logger.reactor("Listening for BGP session(s) on %s:%d" % (self.ip,self.port))

		if not self.daemon.drop_privileges():
			self.logger.reactor("Could not drop privileges to '%s' refusing to run as root" % self.daemon.user,'critical')
			self.logger.reactor("Set the environmemnt value exabgp.daemon.user to change the unprivileged user",'critical')
			return

		# This is required to make sure we can write in the log location as we now have dropped root privileges
		if not self.logger.restart():
			self.logger.reactor("Could not setup the logger, aborting",'critical')
			return

		self.daemon.daemonise()

		if not self.daemon.savepid():
			self.logger.reactor('could not update PID, not starting','error')

		# Make sure we create processes one we have dropped privileges and closed file descriptor
		self.processes = Processes(self)
		self.reload()

		# did we complete the run of updates caused by the last SIGUSR1/SIGUSR2 ?
		reload_completed = True

		wait = environment.settings().tcp.delay
		if wait:
			sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
			self.logger.reactor("waiting for %d seconds before connecting" % sleeptime)
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

					peers = self._peers.keys()

					# handle keepalive first and foremost
					for key in peers:
						peer = self._peers[key]
						if peer.established():
							if peer.keepalive() is False:
								self.logger.reactor("problem with keepalive for peer %s " % peer.neighbor.name(),'error')
								# unschedule the peer

					# Handle all connection
					ios = []
					while peers:
						for key in peers[:]:
							peer = self._peers[key]
							action = peer.run()
							# .run() returns an ACTION enum:
							# * immediate if it wants to be called again
							# * later if it should be called again but has no work atm
							# * close if it is finished and is closing down, or restarting
							if action == ACTION.close:
								self.unschedule(peer)
								peers.remove(key)
							elif action == ACTION.later:
								ios.extend(peer.sockets())
								# no need to come back to it before a a full cycle
								peers.remove(key)

							# give some time to our local processes
							if self.schedule(self.processes.received()) or self._pending:
								self._pending = list(self.run_pending(self._pending))

						duration = time.time() - start
						if duration >= self.max_loop_time:
							ios=[]
							break

					if not peers:
						reload_completed = True

					# append here after reading as if read fails due to a dead process
					# we may respawn the process which changes the FD
					ios.extend(self.processes.fds())

					# RFC state that we MUST not send more than one KEEPALIVE / sec
					# And doing less could cause the session to drop

					while self.schedule(self.processes.received()) or self._pending:
						self._pending = list(self.run_pending(self._pending))

						duration = time.time() - start
						if duration >= self.max_loop_time:
							break

					if self.listener:
						for connection in self.listener.connected():
							# found
							# * False, not peer found for this TCP connection
							# * True, peer found
							# * None, conflict found for this TCP connections
							found = False
							for key in self._peers:
								peer = self._peers[key]
								neighbor = peer.neighbor
								# XXX: FIXME: Inet can only be compared to Inet
								if connection.local == str(neighbor.peer_address) and connection.peer == str(neighbor.local_address):
									if peer.incoming(connection):
										found = True
										break
									found = None
									break

							if found:
								self.logger.reactor("accepted connection from  %s - %s" % (connection.local,connection.peer))
							elif found is False:
								self.logger.reactor("no session configured for  %s - %s" % (connection.local,connection.peer))
								connection.notification(6,3,'no session configured for the peer')
								connection.close()
							elif found is None:
								self.logger.reactor("connection refused (already connected to the peer) %s - %s" % (connection.local,connection.peer))
								connection.notification(6,5,'could not accept the connection')
								connection.close()

					delay = max(start+self.max_loop_time-time.time(),0.0)

					# if we are not already late in this loop !
					if delay:
						# some peers indicated that they wished to be called later
						# so we are waiting for an update on their socket / pipe for up to the rest of the second
						if ios:
							try:
								read,_,_ = select.select(ios,[],[],delay)
							except select.error,e:
								errno,message = e.args
								if not errno in error.block:
									raise e
							# we can still loop here very fast if something goes wrogn with the FD
						else:
							time.sleep(delay)

				self.processes.terminate()
				self.daemon.removepid()
				break
			except KeyboardInterrupt:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("^C received")
						break
					except KeyboardInterrupt:
						pass
			except SystemExit:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("exiting")
						break
					except KeyboardInterrupt:
						pass
			except IOError:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("I/O Error received, most likely ^C during IO",'warning')
						break
					except KeyboardInterrupt:
						pass
			except ProcessError:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("Problem when sending message(s) to helper program, stopping",'error')
						break
					except KeyboardInterrupt:
						pass
			except select.error,e:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("problem using select, stopping",'error')
						break
					except KeyboardInterrupt:
						pass
#				from exabgp.leak import objgraph
#				print objgraph.show_most_common_types(limit=20)
#				import random
#				obj = objgraph.by_type('Route')[random.randint(0,2000)]
#				objgraph.show_backrefs([obj], max_depth=10)

	def shutdown (self):
		"""terminate all the current BGP connections"""
		self.logger.reactor("Performing shutdown")
		if self.listener:
			self.listener.stop()
		for key in self._peers.keys():
			self._peers[key].stop()

	def reload (self,restart=False):
		"""reload the configuration and send to the peer the route which changed"""
		self.logger.reactor("Performing reload of exabgp %s" % version)

		reloaded = self.configuration.reload()

		if not reloaded:
			self.logger.configuration("Problem with the configuration file, no change done",'error')
			self.logger.configuration(self.configuration.error,'error')
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
			# modified peer
			elif self._peers[key].neighbor != neighbor:
				self.logger.reactor("Peer definition change, restarting %s" % str(key))
				self._peers[key].restart(neighbor)
			# same peer but perhaps not the routes
			else:
				self._peers[key].send_new(neighbor.rib.outgoing.queued_changes())
		self.logger.configuration("Loaded new configuration successfully",'warning')
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
			except KeyboardInterrupt:
				self._shutdown = True
				self.logger.reactor("^C received",'error')
				break

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
					for change in list(neighbor.rib.outgoing.sent_changes()):
						self._answer(service,'neighbor %s %s' % (neighbor.local_address,str(change.nlri)))
						yield True
			self._pending.append(_show_route(self))
			return True

		if command == 'show routes extensive':
			def _show_extensive (self):
				for key in self.configuration.neighbor.keys():
					neighbor = self.configuration.neighbor[key]
					for change in list(neighbor.rib.outgoing.sent_changes()):
						self._answer(service,'neighbor %s %s' % (neighbor.name(),change.extensive()))
						yield True
			self._pending.append(_show_extensive(self))
			return True

		# watchdog
		if command.startswith('announce watchdog'):
			def _announce_watchdog (self,name):
				for neighbor in self.configuration.neighbor:
					self.configuration.neighbor[neighbor].rib.outgoing.announce_watchdog(name)
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
					self.configuration.neighbor[neighbor].rib.outgoing.withdraw_watchdog(name)
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
			# This function returns a list and a string
			# The first list contains parsed neighbor to match against our defined peers
			# The string is the command to be run for those peers
			# The parsed neighbor is a list of the element making the neighbor string so each part can be checked against the neighbor name

			returned = []
			neighbor,remaining = command.split(' ',1)
			if neighbor != 'neighbor':
				return [],command

			ip,command = remaining.split(' ',1)
			definition = ['neighbor %s' % (ip)]

			while True:
				try:
					key,value,remaining = command.split(' ',2)
				except ValueError:
					key,value = command.split(' ',1)
				if key == ',':
					returned.append(definition)
					_,command = command.split(' ',1)
					definition = []
					continue
				if key not in ['neighbor','local-ip','local-as','peer-as','router-id','family-allowed']:
					if definition:
						returned.append(definition)
					break
				definition.append('%s %s' % (key,value))
				command = remaining

			return returned,command

		def match_neighbor (description,name):
			for string in description:
				if re.search('(^|[\s])%s($|[\s,])' % re.escape(string), name) is None:
					return False
			return True

		def match_neighbors (descriptions,peers):
			"returns the sublist of peers matching the description passed, or None if no description is given"
			if not descriptions:
				return peers.keys()

			returned = []
			for key in peers:
				for description in descriptions:
					if match_neighbor(description,key):
						if key not in returned:
							returned.append(key)
			return returned

		# route announcement / withdrawal
		if 'announce route ' in command:
			def _announce_change (self,command,nexthops):
				changes = self.configuration.parse_api_route(command,nexthops,'announce')
				if not changes:
					self.logger.reactor("Command could not parse route in : %s" % command,'warning')
					yield True
				else:
					peers = []
					for (peer,change) in changes:
						peers.append(peer)
						self.configuration.change_to_peers(change,[peer,])
						yield False
					self.logger.reactor("Route added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				nexthops = dict((peer,self._peers[peer].neighbor.local_address) for peer in peers)
				self._pending.append(_announce_change(self,command,nexthops))
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		# route announcement / withdrawal
		if 'flush route' in command:  # This allows flush routes with a s to work
			def _flush (self,peers):
				self.logger.reactor("Flushing routes for %s" % ', '.join(peers if peers else []) if peers is not None else 'all peers')
				yield True
				self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				self._pending.append(_flush(self,peers))
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		if 'withdraw route' in command:
			def _withdraw_change (self,command,nexthops):
				changes = self.configuration.parse_api_route(command,nexthops,'withdraw')
				if not changes:
					self.logger.reactor("Command could not parse route in : %s" % command,'warning')
					yield True
				else:
					for (peer,change) in changes:
						if self.configuration.change_to_peers(change,[peer,]):
							self.logger.reactor("Route removed : %s" % change.extensive())
							yield False
						else:
							self.logger.reactor("Could not find therefore remove route : %s" % change.extensive(),'warning')
							yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				nexthops = dict((peer,self._peers[peer].neighbor.local_address) for peer in peers)
				self._pending.append(_withdraw_change(self,command,nexthops))
				return True
			except ValueError:
				pass
			except IndexError:
				pass


		# attribute announcement / withdrawal
		if 'announce attribute ' in command:
			def _announce_attribute (self,command,nexthops):
				changes = self.configuration.parse_api_attribute(command,nexthops,'announce')
				if not changes:
					self.logger.reactor("Command could not parse attribute in : %s" % command,'warning')
					yield True
				else:
					for (peers,change) in changes:
						self.configuration.change_to_peers(change,peers)
						self.logger.reactor("Route added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
					yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				nexthops = dict((peer,self._peers[peer].neighbor.local_address) for peer in peers)
				self._pending.append(_announce_attribute(self,command,nexthops))
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		# attribute announcement / withdrawal
		if 'withdraw attribute ' in command:
			def _withdraw_attribute (self,command,nexthops):
				changes = self.configuration.parse_api_attribute(command,nexthops,'withdraw')
				if not changes:
					self.logger.reactor("Command could not parse attribute in : %s" % command,'warning')
					yield True
				else:
					for (peers,change) in changes:
						if self.configuration.change_to_peers(change,peers):
							self.logger.reactor("Route removed : %s" % change.extensive())
							yield False
						else:
							self.logger.reactor("Could not find therefore remove route : %s" % change.extensive(),'warning')
							yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				nexthops = dict((peer,self._peers[peer].neighbor.local_address) for peer in peers)
				self._pending.append(_withdraw_attribute(self,command,nexthops))
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		# flow announcement / withdrawal
		if 'announce flow' in command:
			def _announce_flow (self,command,peers):
				changes = self.configuration.parse_api_flow(command,'announce')
				if not changes:
					self.logger.reactor("Command could not parse flow in : %s" % command)
					yield True
				else:
					for change in changes:
						self.configuration.change_to_peers(change,peers)
						self.logger.reactor("Flow added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
						yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				self._pending.append(_announce_flow(self,command,peers))
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		if 'withdraw flow' in command:
			def _withdraw_flow (self,command,peers):
				changes = self.configuration.parse_api_flow(command,'withdraw')
				if not changes:
					self.logger.reactor("Command could not parse flow in : %s" % command)
					yield True
				else:
					for change in changes:
						if self.configuration.change_to_peers(change,peers):
							self.logger.reactor("Flow found and removed : %s" % change.extensive())
							yield False
						else:
							self.logger.reactor("Could not find therefore remove flow : %s" % change.extensive(),'warning')
							yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				self._pending.append(_withdraw_flow(self,command,peers))
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
							self.logger.reactor('teardown scheduled for %s' % ' '.join(description))
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		if 'announce route-refresh' in command:
			def _announce_refresh (self,command,peers):
				rr = self.configuration.parse_api_refresh(command)
				if not rr:
					self.logger.reactor("Command could not parse flow in : %s" % command)
					yield True
				else:
					self.configuration.refresh_to_peers(rr,peers)
					self.logger.reactor("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',rr.extensive()))
					yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				self._pending.append(_announce_refresh(self,command,peers))
				return True
			except ValueError:
				pass
			except IndexError:
				pass

		if command.startswith('operational ') and (command.split() + ['safe'])[1].lower() in ('asm','adm','rpcq','rpcp','apcq','apcp','lpcq','lpcp'):
			def _announce_operational (self,command,peers):
				operational = self.configuration.parse_api_operational(command)
				if not operational:
					self.logger.reactor("Command could not parse operational command : %s" % command)
					yield True
				else:
					self.configuration.operational_to_peers(operational,peers)
					self.logger.reactor("operational message sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',operational.extensive()))
					yield False
					self._route_update = True

			try:
				descriptions,command = extract_neighbors(command)
				peers = match_neighbors(descriptions,self._peers)
				if peers == []:
					self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
					return False
				self._pending.append(_announce_operational(self,command,peers))
				return True
			except ValueError:
				pass
			except IndexError:
				pass


		# unknown
		self.logger.reactor("Command from process not understood : %s" % command,'warning')
		return False

	def _answer (self,service,string):
		self.processes.write(service,string)
		self.logger.reactor('Responding to %s : %s' % (service,string))


	def route_update (self):
		"""the process ran and we need to figure what routes to changes"""
		self.logger.reactor("Performing dynamic route update")
		for key in self.configuration.neighbor.keys():
			self._peers[key].send_new()
		self.logger.reactor("Updated peers dynamic routes successfully")

	def route_flush (self):
		"""we just want to flush any unflushed routes"""
		self.logger.reactor("Performing route flush")
		for key in self.configuration.neighbor.keys():
			self._peers[key].send_new(update=True)

	def restart (self):
		"""kill the BGP session and restart it"""
		self.logger.reactor("Performing restart of exabgp %s" % version)
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
