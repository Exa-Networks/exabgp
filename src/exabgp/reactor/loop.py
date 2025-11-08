# encoding: utf-8
"""
reactor/loop.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import re
import time

from exabgp.reactor.daemon import Daemon
from exabgp.reactor.listener import Listener
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.api.processes import ProcessError
from exabgp.reactor.peer import Peer
from exabgp.reactor.interrupt import Signal

from exabgp.reactor.api import API
from exabgp.configuration.process import API_PREFIX
from exabgp.environment import getenv

from exabgp.bgp.fsm import FSM

from exabgp.version import version
from exabgp.logger import log


class AsyncScheduler:
    """Adapter to bridge old asynchronous scheduler API to asyncio.
    The old API command handlers call reactor.asynchronous.schedule() to run
    generators. These generators are simple and just do work then yield a few
    times before completing. We can run them synchronously to completion."""

    def __init__(self):
        pass

    def schedule(self, service, description, generator):
        """Run a generator to completion synchronously.
        The generators from API command handlers are simple - they do some work,
        yield a few boolean values, then complete. They don't need to be async."""
        try:
            # Run the generator to completion
            result = None
            while True:
                try:
                    result = generator.send(result)
                    # Continue to next yield
                except StopIteration:
                    # Generator completed normally
                    break
        except Exception as exc:
            log.debug(f'Error in scheduled task {service}/{description}: {exc}', 'reactor')

    def clear(self, service):
        """Clear is a no-op since we run generators synchronously."""
        pass


class Reactor(object):
    class Exit(object):
        normal = 0
        validate = 0
        listening = 1
        configuration = 1
        privileges = 1
        log = 1
        pid = 1
        socket = 1
        io_error = 1
        process = 1
        select = 1
        unknown = 1

    # [hex(ord(c)) for c in os.popen('clear').read()]
    clear = b''.join(bytes([int(c, 16)]) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a'])

    def __init__(self, configuration):
        self._ips = getenv().tcp.bind
        self._port = getenv().tcp.port
        self._stopping = getenv().tcp.attempts > 0
        self.exit_code = self.Exit.unknown

        self.max_loop_time = getenv().reactor.speed
        self._sleep_time = self.max_loop_time / 100
        self._ratelimit = {}
        self.early_drop = getenv().daemon.drop

        self.processes = None

        self.configuration = configuration
        self.signal = Signal()
        self.daemon = Daemon(self)
        self.listener = Listener(self)
        self.api = API(self)
        self.asynchronous = AsyncScheduler()  # Adapter for old async scheduler API

        self._peers = {}
        self._peer_tasks = {}  # Track asyncio tasks for each peer

        self._saved_pid = False

    def _termination(self, reason, exit_code):
        self.exit_code = exit_code
        self.signal.received = Signal.SHUTDOWN
        log.critical(reason, 'reactor')

    def _rate_limited(self, peer, rate):
        if rate <= 0:
            return False
        second = int(time.time())
        ratelimit = self._ratelimit.get(peer, {})
        if second not in ratelimit:
            self._ratelimit[peer] = {second: rate - 1}
            return False
        if self._ratelimit[peer][second] > 0:
            self._ratelimit[peer][second] -= 1
            return False
        return True

    # peer related functions

    def active_peers(self):
        peers = set()
        for key, peer in self._peers.items():
            if peer.neighbor['passive'] and not peer.proto:
                continue
            peers.add(key)
        return peers

    def established_peers(self):
        peers = set()
        for key, peer in self._peers.items():
            if peer.fsm == FSM.ESTABLISHED:
                peers.add(key)
        return peers

    def peers(self, service=''):
        matching = []
        for peer_name, peer in self._peers.items():
            if service == '':
                matching.append(peer_name)
                continue
            if service.startswith(API_PREFIX):
                matching.append(peer_name)
                continue
            if service in peer.neighbor.api['processes']:
                matching.append(peer_name)
                continue
            if any(True for r in peer.neighbor.api['processes-match'] if re.match(r, service)):
                matching.append(peer_name)
                continue

        return matching

    async def handle_connection(self, peer_name, connection):
        """Handle incoming connection for a peer"""
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return
        return await peer.handle_connection(connection)

    def neighbor(self, peer_name):
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return
        return peer.neighbor

    def neighbor_name(self, peer_name):
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return ''
        return peer.neighbor.name()

    def neighbor_ip(self, peer_name):
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return ''
        return str(peer.neighbor['peer-address'])

    def neighbor_cli_data(self, peer_name):
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return ''
        return peer.cli_data()

    def neighor_rib(self, peer_name, rib_name, advertised=False):
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return []
        families = None
        if advertised:
            families = peer.proto.negotiated.families if peer.proto else []
        rib = peer.neighbor.rib.outgoing if rib_name == 'out' else peer.neighbor.rib.incoming
        return list(rib.cached_changes(families))

    def neighbor_rib_resend(self, peer_name):
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return
        peer.resend(peer.neighbor['capability']['route-refresh'])

    def neighbor_rib_out_withdraw(self, peer_name):
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return
        peer.neighbor.rib.outgoing.withdraw()

    def neighbor_rib_in_clear(self, peer_name):
        peer = self._peers.get(peer_name, None)
        if not peer:
            log.critical('could not find referenced peer', 'reactor')
            return
        peer.neighbor.rib.incoming.clear()

    # ...

    def _pending_adjribout(self):
        for peer in self.active_peers():
            if self._peers[peer].neighbor.rib.outgoing.pending():
                return True
        return False

    def check(self, route, nlri_only=False):
        from exabgp.configuration.check import check_message
        from exabgp.configuration.check import check_nlri

        if not self.reload():
            return False

        check = check_nlri if nlri_only else check_message

        neighbors = self.configuration.neighbors
        for neighbor in neighbors.values():
            if not check(neighbor, route):
                return False
        return True

    def display(self, route, nlri_only=False):
        from exabgp.configuration.check import display_message
        from exabgp.configuration.check import display_nlri

        if not self.reload():
            return False

        display = display_nlri if nlri_only else display_message

        neighbors = self.configuration.neighbors
        for neighbor in neighbors.values():
            if not display(neighbor, route):
                return False
        return True

    def run(self):
        """Main entry point - sets up and runs the async event loop"""
        self.daemon.daemonise()

        # Make sure we create processes once we have closed file descriptor
        # unfortunately, this must be done before reading the configuration file
        # so we can not do it with dropped privileges
        self.processes = Processes()

        # we have to read the configuration possibly with root privileges
        # as we need the MD5 information when we bind, and root is needed
        # to bind to a port < 1024

        # this is undesirable as :
        # - handling user generated data as root should be avoided
        # - we may not be able to reload the configuration once the privileges are dropped

        # but I can not see any way to avoid it
        for ip in self._ips:
            if not self.listener.listen_on(ip, None, self._port, None, False, None):
                return self.Exit.listening

        if not self.reload():
            return self.Exit.configuration

        for neighbor in self.configuration.neighbors.values():
            if neighbor['listen']:
                if not self.listener.listen_on(
                    neighbor['md5-ip'],
                    neighbor['peer-address'],
                    neighbor['listen'],
                    neighbor['md5-password'],
                    neighbor['md5-base64'],
                    neighbor['incoming-ttl'],
                ):
                    return self.Exit.listening

        if not self.early_drop:
            self.processes.start(self.configuration.processes)

        if not self.daemon.drop_privileges():
            log.critical("could not drop privileges to '%s' refusing to run as root" % self.daemon.user, 'reactor')
            log.critical('set the environmemnt value exabgp.daemon.user to change the unprivileged user', 'reactor')
            return self.Exit.privileges

        if self.early_drop:
            self.processes.start(self.configuration.processes)

        # This is required to make sure we can write in the log location as we now have dropped root privileges
        log.init(getenv())

        if not self.daemon.savepid():
            return self.Exit.pid

        wait = getenv().tcp.delay
        if wait:
            sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
            log.debug('waiting for %d seconds before connecting' % sleeptime, 'reactor')
            time.sleep(float(sleeptime))

        # Run the async event loop
        try:
            asyncio.run(self._async_run())
        except KeyboardInterrupt:
            self._termination('^C received', self.Exit.normal)
        except SystemExit:
            self._termination('exiting', self.Exit.normal)
        except ProcessError:
            self._termination('Problem when sending message(s) to helper program, stopping', self.Exit.process)

        return self.exit_code

    async def _async_run(self):
        """Main async event loop"""
        # Create tasks for all peers
        for key in list(self._peers.keys()):
            if key not in self._peer_tasks:
                peer = self._peers[key]
                self._peer_tasks[key] = asyncio.create_task(peer.run())

        # Create listener task for incoming connections
        listener_task = asyncio.create_task(self._listen_loop())

        # Create signal handler task
        signal_task = asyncio.create_task(self._signal_loop())

        # Create API command processing task
        api_task = asyncio.create_task(self._api_loop())

        # Create termination checker task (for tcp.once mode)
        termination_task = asyncio.create_task(self._termination_loop())

        # Wait for shutdown
        try:
            await asyncio.gather(
                listener_task,
                signal_task,
                api_task,
                termination_task,
                *self._peer_tasks.values(),
                return_exceptions=True
            )
        except Exception as exc:
            log.debug(f'Exception in main loop: {exc}', 'reactor')

    async def _termination_loop(self):
        """Check for termination conditions (tcp.once, no peers, etc.)"""
        while True:
            await asyncio.sleep(0.5)

            # Clean up completed peer tasks
            for key in list(self._peer_tasks.keys()):
                if self._peer_tasks[key].done():
                    del self._peer_tasks[key]
                    # If peer still exists and is stopped, remove it
                    if key in self._peers and not self._peers[key]._restart:
                        del self._peers[key]

            # Check if we should exit due to tcp.once with no peers
            if self._stopping and not self._peers.keys():
                self._termination('exiting on peer termination', self.Exit.normal)
                return

    async def _listen_loop(self):
        """Handle incoming connections"""
        while not self.signal.received == Signal.SHUTDOWN:
            try:
                if self.listener.incoming():
                    await self.listener.new_connections()
                await asyncio.sleep(0.1)  # Brief pause between checks
            except Exception as exc:
                log.debug(f'Error in listener loop: {exc}', 'reactor')

    async def _signal_loop(self):
        """Handle signals (SIGHUP, SIGUSR1, etc.)"""
        while True:
            await asyncio.sleep(0.5)  # Check for signals periodically

            if not self.signal.received:
                continue

            signaled = self.signal.received

            # report that we received a signal
            for key in self._peers:
                if self._peers[key].neighbor.api['signal']:
                    self._peers[key].reactor.processes.signal(self._peers[key].neighbor, self.signal.number)

            self.signal.rearm()

            # we always want to exit
            if signaled == Signal.SHUTDOWN:
                self.exit_code = self.Exit.normal
                self.shutdown()
                return

            # it does not matter what we did if we are restarting
            # as the peers and network stack are replaced by new ones
            if signaled == Signal.RESTART:
                self.restart()
                continue

            # did we complete the run of updates caused by the last SIGUSR1/SIGUSR2 ?
            if self._pending_adjribout():
                continue

            if signaled == Signal.RELOAD:
                self.reload()
                self.processes.start(self.configuration.processes, False)
                continue

            if signaled == Signal.FULL_RELOAD:
                self.reload()
                self.processes.start(self.configuration.processes, True)
                continue

    async def _api_loop(self):
        """Process API commands from helper processes"""
        loop = asyncio.get_running_loop()
        log.debug('API loop started', 'reactor')
        iteration = 0
        while not self.signal.received == Signal.SHUTDOWN:
            try:
                iteration += 1
                if iteration % 100 == 1:
                    log.debug(f'API loop iteration {iteration}', 'reactor')

                # Get commands from helper processes in an executor to avoid blocking
                # Uses received_list() which collects all available commands
                commands = await loop.run_in_executor(None, self.processes.received_list)

                if commands:
                    log.debug(f'API loop received {len(commands)} commands', 'reactor')

                # Process all commands
                for service, command in commands:
                    self.api.process(self, service, command)

                # Brief delay between polling cycles
                await asyncio.sleep(0.01)
            except Exception as exc:
                log.debug(f'Error in API loop: {exc}', 'reactor')
                await asyncio.sleep(0.1)
        log.debug('API loop exiting', 'reactor')

    def register_peer(self, name, peer):
        self._peers[name] = peer

    def teardown_peer(self, name, code):
        self._peers[name].teardown(code)

    def shutdown(self):
        """Terminate all the current BGP connections"""
        log.critical('performing shutdown', 'reactor')
        if self.listener:
            self.listener.stop()
            self.listener = None
        for key in self._peers.keys():
            self._peers[key].shutdown()
        # Cancel all peer tasks
        for task in self._peer_tasks.values():
            if not task.done():
                task.cancel()
        self._peer_tasks.clear()
        self.processes.terminate()
        self.daemon.removepid()
        self._stopping = True

    def reload(self):
        """Reload the configuration and send to the peer the route which changed"""
        log.info('performing reload of exabgp %s' % version, 'configuration')

        reloaded = self.configuration.reload()

        if not reloaded:
            log.error('could not load/reload configuration', 'configuration')
            log.error(str(self.configuration.error), 'configuration')
            return False

        # Remove peers that are no longer in configuration
        for key, peer in list(self._peers.items()):
            if key not in self.configuration.neighbors:
                log.debug('removing peer: %s' % peer.neighbor.name(), 'reactor')
                peer.remove()
                # Cancel the peer's task
                if key in self._peer_tasks:
                    self._peer_tasks[key].cancel()
                    del self._peer_tasks[key]

        # Add or update peers
        for key, neighbor in self.configuration.neighbors.items():
            # new peer
            if key not in self._peers:
                log.debug('new peer: %s' % neighbor.name(), 'reactor')
                peer = Peer(neighbor, self)
                self._peers[key] = peer
                # Create task for new peer if we're in the async context
                try:
                    loop = asyncio.get_running_loop()
                    self._peer_tasks[key] = loop.create_task(peer.run())
                except RuntimeError:
                    # Not in async context yet (initial load)
                    pass
            # modified peer
            elif self._peers[key].neighbor != neighbor:
                log.debug('peer definition change, establishing a new connection for %s' % str(key), 'reactor')
                self._peers[key].reestablish(neighbor)
            # same peer but perhaps not the routes
            else:
                # finding what route changed and sending the delta is not obvious
                log.debug('peer definition identical, updating peer routes if required for %s' % str(key), 'reactor')
                self._peers[key].reconfigure(neighbor)
            for ip in self._ips:
                if ip.afi == neighbor['peer-address'].afi:
                    self.listener.listen_on(
                        ip, neighbor['peer-address'], self._port, neighbor['md5-password'], neighbor['md5-base64'], None
                    )
        log.info('loaded new configuration successfully', 'reactor')

        return True

    def restart(self):
        """Kill the BGP session and restart it"""
        log.info('performing restart of exabgp %s' % version, 'reactor')

        reloaded = self.configuration.reload()

        if not reloaded:
            # XXX: FIXME: Could return False, in case there is interference with old config...
            pass

        for key in self._peers.keys():
            if key not in self.configuration.neighbors.keys():
                peer = self._peers[key]
                log.debug('removing peer %s' % peer.neighbor.name(), 'reactor')
                self._peers[key].remove()
            else:
                self._peers[key].reestablish()
        self.processes.start(self.configuration.processes, True)

    # def nexthops (self, peers):
    # 	return dict((peer,self._peers[peer].neighbor['local-address']) for peer in peers)
