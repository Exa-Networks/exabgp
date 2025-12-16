"""Main reactor event loop for ExaBGP.

The Reactor is the central coordinator managing BGP peers, API processes,
configuration reloading, and signal handling. Supports both generator-based
(legacy) and asyncio operation modes.

Key classes:
    Reactor: Main event loop and peer manager

Key responsibilities:
    - Manage peer lifecycle (create, restart, remove)
    - Handle configuration reload (SIGUSR1)
    - Coordinate API command processing
    - Signal handling (SIGTERM, SIGHUP, etc.)

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import errno
import re
import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.fsm import FSM
from exabgp.configuration.process import API_PREFIX
from exabgp.environment import getenv
from exabgp.logger import lazyexc, lazymsg, log
from exabgp.reactor.api import API
from exabgp.reactor.api.processes import ProcessError, Processes
from exabgp.reactor.asynchronous import ASYNC
from exabgp.reactor.daemon import Daemon
from exabgp.reactor.interrupt import Signal
from exabgp.reactor.listener import Listener
from exabgp.reactor.peer import Peer
from exabgp.reactor.timing import LoopTimer
from exabgp.rib.route import Route
from exabgp.version import version


class Reactor:
    class Exit:
        normal: int = 0
        validate: int = 0
        listening: int = 1
        configuration: int = 1
        privileges: int = 1
        log: int = 1
        pid: int = 1
        socket: int = 1
        io_error: int = 1
        process: int = 1
        select: int = 1
        unknown: int = 1

    # [hex(ord(c)) for c in os.popen('clear').read()]
    clear: bytes = b''.join(bytes([int(c, 16)]) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a'])

    def __init__(self, configuration: Any) -> None:
        self._ips: list[Any] = getenv().tcp.bind
        self._port: int = getenv().tcp.port
        self._stopping: bool = getenv().tcp.attempts > 0
        self.exit_code: int = self.Exit.unknown

        # Daemon identity for CLI health monitoring
        self.daemon_uuid: str = str(uuid.uuid4())
        self.daemon_start_time: float = time.time()

        # Active CLI client tracking (multi-client support)
        self.active_clients: dict[str, float] = {}  # uuid -> last_ping_time

        self.max_loop_time: float = getenv().reactor.speed
        self._sleep_time: float = self.max_loop_time / 100
        self._busyspin: dict[int, int] = {}
        self._ratelimit: dict[str, dict[int, int]] = {}
        self.early_drop: bool = getenv().daemon.drop

        self.processes: Processes

        self.configuration: Any = configuration
        self.asynchronous: ASYNC = ASYNC()
        self.signal: Signal = Signal()
        self.daemon: Daemon = Daemon(self)
        self.listener: Listener = Listener(self)
        self.api: API = API(self)

        self._peers: dict[str, Peer] = {}
        self._dynamic_peers: set[str] = set()  # Dynamic peers created via API

        self._saved_pid: bool = False

    def _termination(self, reason: str, exit_code: int) -> None:
        self.exit_code = exit_code
        self.signal.received = Signal.SHUTDOWN
        log.critical(lazymsg('reactor.termination reason={r}', r=reason), 'reactor')

    def _prevent_spin(self) -> bool:
        second: int = int(time.time())
        if second not in self._busyspin:
            self._busyspin = {second: 0}
        self._busyspin[second] += 1
        if self._busyspin[second] > self.max_loop_time:
            time.sleep(self._sleep_time)
            return True
        return False

    def _rate_limited(self, peer: str, rate: int) -> bool:
        if rate <= 0:
            return False
        second: int = int(time.time())
        ratelimit: dict[int, int] = self._ratelimit.get(peer, {})
        if second not in ratelimit:
            self._ratelimit[peer] = {second: rate - 1}
            return False
        if self._ratelimit[peer][second] > 0:
            self._ratelimit[peer][second] -= 1
            return False
        return True

    async def _wait_for_io(self, sleeptime: int) -> list[int]:
        """Wait for I/O using asyncio (async version)

        Async wrapper for event loop integration.
        This is a simplified version for the hybrid approach foundation.
        Full integration will use asyncio I/O multiplexing.

        Args:
            sleeptime: Milliseconds to wait

        Returns:
            List of ready file descriptors (empty in this foundation version)
        """
        # Convert milliseconds to seconds
        sleep_seconds = sleeptime / 1000.0

        try:
            # Use asyncio.sleep for cooperative yielding
            await asyncio.sleep(sleep_seconds)

            # Return empty list (foundation version)
            # Full implementation will integrate with asyncio I/O
            return []

        except KeyboardInterrupt:
            self._termination('^C received', self.Exit.normal)
            return []
        except (OSError, asyncio.CancelledError):
            self._prevent_spin()
            return []

    async def _run_async_peers(self) -> None:
        """Run all active peers concurrently as asyncio tasks

        This method manages peer lifecycle:
        - Creates async tasks for each peer
        - Monitors task completion/failure
        - Handles peer removal when tasks complete
        - Coordinates concurrent peer execution
        - Applies rate limiting (matches sync mode line 565)
        """
        # Start all active peers as async tasks
        for key in self.active_peers():
            peer = self._peers[key]

            # Limit the number of message handling per second (matches sync mode)
            if self._rate_limited(key, peer.neighbor.rate_limit):
                continue

            if peer._async_task is None:
                peer.start_async_task()

        # Wait briefly to allow tasks to run
        await asyncio.sleep(0)

        # Check for completed/failed peers
        completed_peers = []
        for key in list(self._peers.keys()):
            peer = self._peers[key]
            if peer._async_task is not None:
                if peer._async_task.done():
                    try:
                        # Check if task raised an exception
                        peer._async_task.result()
                    except Exception as exc:
                        log.error(lazyexc('peer.task.failed peer={key} error={exc}', exc, key=key), 'reactor')
                    completed_peers.append(key)

        # Remove completed peers
        for key in completed_peers:
            if key in self._peers:
                del self._peers[key]

    async def _async_main_loop(self) -> None:
        """Async version of the main event loop

        This replaces the generator-based event loop in run() with
        async/await patterns while maintaining identical behavior.

        NOTE: In async mode, we use minimal sleep (asyncio.sleep(0)) to yield
        control to peer tasks while processing events as fast as possible.
        The asyncio event loop handles I/O waiting automatically.
        """
        # Timing instrumentation for performance analysis
        loop_timer = LoopTimer('async_main_loop', warn_threshold_ms=100)

        while True:
            loop_timer.start()
            try:
                # Handle signals
                if self.signal.received:
                    signaled = self.signal.received

                    # Report signal to peers
                    for key in self._peers:
                        peer = self._peers[key]
                        if peer.neighbor.api and peer.neighbor.api['signal']:
                            peer.reactor.processes.signal(peer.neighbor, self.signal.number)

                    self.signal.rearm()

                    # Handle SHUTDOWN
                    if signaled == Signal.SHUTDOWN:
                        self.exit_code = self.Exit.normal
                        self.shutdown()
                        break

                    # Handle RESTART
                    if signaled == Signal.RESTART:
                        self.restart()
                        continue

                    # Wait for pending adjribout
                    if self._pending_adjribout():
                        continue

                    # Handle RELOAD
                    if signaled == Signal.RELOAD:
                        self.reload()
                        self.processes.start(self.configuration.processes, False)
                        continue

                    # Handle FULL_RELOAD
                    if signaled == Signal.FULL_RELOAD:
                        self.reload()
                        self.processes.start(self.configuration.processes, True)
                        continue

                # Check for incoming connections
                if self.listener.incoming():
                    self.asynchronous.schedule(
                        str(uuid.uuid1()),
                        'checking for new connection(s)',
                        self.listener.new_connections(),
                    )

                # Run all peers concurrently (matches sync mode line 563-597)
                await self._run_async_peers()

                # Process API commands (matches sync mode line 600-602)
                # Read at least one message per process if there is some and parse it
                for service, command in self.processes.received_async():
                    self.api.process(self, service, command)

                # Run async scheduled tasks (matches sync mode line 604)
                # Must use _run_async() instead of run() since event loop is already running
                if self.asynchronous._async:
                    await self.asynchronous._run_async()

                # Flush API process write queue (send ACKs and responses)
                await self.processes.flush_write_queue_async()

                # Yield control to peer tasks (minimal sleep)
                # asyncio event loop handles I/O waiting automatically
                await asyncio.sleep(0)

                # Check if stopping and no peers left
                if self._stopping and not self._peers.keys():
                    self._termination('exiting on peer termination', self.Exit.normal)
                    break

                # Log timing for this iteration
                loop_timer.stop()
                loop_timer.log_if_slow()

            except asyncio.CancelledError:
                # Raised when asyncio.run() cancels tasks (e.g., on Ctrl+C)
                self._termination('^C received', self.Exit.normal)
                break
            except KeyboardInterrupt:
                self._termination('^C received', self.Exit.normal)
                break
            except SystemExit:
                self._termination('exiting', self.Exit.normal)
                break
            except OSError as exc:
                # Handle OS errors
                if exc.errno == errno.EINTR:
                    self._termination('I/O Error received, most likely ^C during IO', self.Exit.io_error)
                elif exc.errno in (errno.EBADF, errno.EINVAL):
                    self._termination('problem using select, stopping', self.Exit.select)
                else:
                    self._termination('socket error received', self.Exit.socket)
                break
            except ProcessError:
                self._termination('Problem when sending message(s) to helper program, stopping', self.Exit.process)
                break

    # peer related functions

    def active_peers(self) -> set[str]:
        peers: set[str] = set()
        for key, peer in self._peers.items():
            if peer.neighbor.session.passive and not peer.proto:
                continue
            peers.add(key)
        return peers

    def established_peers(self) -> set[str]:
        peers: set[str] = set()
        for key, peer in self._peers.items():
            if peer.fsm == FSM.ESTABLISHED:
                peers.add(key)
        return peers

    def peers(self, service: str = '') -> list[str]:
        matching: list[str] = []
        for peer_name, peer in self._peers.items():
            if service == '':
                matching.append(peer_name)
                continue
            if service.startswith(API_PREFIX):
                matching.append(peer_name)
                continue
            if peer.neighbor.api and service in peer.neighbor.api['processes']:
                matching.append(peer_name)
                continue
            if peer.neighbor.api and any(True for r in peer.neighbor.api['processes-match'] if re.match(r, service)):
                matching.append(peer_name)
                continue

        return matching

    def handle_connection(self, peer_name: str, connection: Any) -> Any:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=incoming_connection', p=peer_name), 'reactor')
            return None
        return peer.handle_connection(connection)

    def neighbor(self, peer_name: str) -> 'Neighbor' | None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=neighbor_lookup', p=peer_name), 'reactor')
            return None
        return peer.neighbor

    def neighbor_name(self, peer_name: str) -> str:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=name_lookup', p=peer_name), 'reactor')
            return ''
        return peer.neighbor.name()

    def neighbor_ip(self, peer_name: str) -> str:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=ip_lookup', p=peer_name), 'reactor')
            return ''
        return str(peer.neighbor.session.peer_address)

    def neighbor_cli_data(self, peer_name: str) -> dict[str, Any]:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=cli_data', p=peer_name), 'reactor')
            return {}
        return peer.cli_data()

    def neighor_rib(self, peer_name: str, rib_name: str, advertised: bool = False) -> list[Route]:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=rib_lookup', p=peer_name), 'reactor')
            return []
        families: list[Any] | None = None
        if advertised:
            families = peer.proto.negotiated.families if peer.proto else []
        rib = peer.neighbor.rib.outgoing if rib_name == 'out' else peer.neighbor.rib.incoming
        return list(rib.cached_routes(families))

    def neighbor_rib_resend(self, peer_name: str) -> None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=rib_resend', p=peer_name), 'reactor')
            return
        peer.resend(bool(peer.neighbor.capability.route_refresh))

    def neighbor_rib_out_withdraw(self, peer_name: str) -> None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=outgoing_withdraw', p=peer_name), 'reactor')
            return
        peer.neighbor.rib.outgoing.withdraw()

    def neighbor_rib_in_clear(self, peer_name: str) -> None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lazymsg('peer.notfound peer={p} operation=incoming_clear', p=peer_name), 'reactor')
            return
        peer.neighbor.rib.incoming.clear()

    # ...

    def _pending_adjribout(self) -> bool:
        for peer in self.active_peers():
            rib = self._peers[peer].neighbor.rib
            if rib.outgoing.pending():
                return True
        return False

    def check(self, route: str, nlri_only: bool = False) -> bool:
        from exabgp.configuration.check import check_message, check_nlri

        if not self.reload():
            return False

        check = check_nlri if nlri_only else check_message

        neighbors = self.configuration.neighbors
        for neighbor in neighbors.values():
            if not check(neighbor, route):
                return False
        return True

    def display(self, route: str, nlri_only: bool = False, generic: bool = False, command: bool = False) -> bool:
        from exabgp.configuration.check import display_message, display_nlri

        if not self.reload():
            return False

        neighbors = self.configuration.neighbors
        for neighbor in neighbors.values():
            if nlri_only:
                if not display_nlri(neighbor, route):
                    return False
            else:
                if not display_message(neighbor, route, generic=generic, command=command):
                    return False
        return True

    def run(self) -> int:
        """Main entry point - runs the asyncio event loop."""
        return asyncio.run(self.run_async())

    async def run_async(self) -> int:
        """Async version of run() - main entry point for asyncio mode

        Performs the same setup as run() but uses async event loop.
        """
        self.daemon.daemonise()

        # Create processes after closing file descriptors
        self.processes = Processes()

        # Setup listeners
        for ip in self._ips:
            if not self.listener.listen_on(ip, None, self._port, None, False, None):
                log.critical(
                    lazymsg('startup.failed.listener ip={ip} port={port}', ip=ip, port=self._port),
                    'reactor',
                )
                return self.Exit.listening

        if not self.reload():
            return self.Exit.configuration

        for neighbor in self.configuration.neighbors.values():
            if neighbor.session.listen:
                if not self.listener.listen_on(
                    neighbor.session.md5_ip,
                    neighbor.session.peer_address,
                    neighbor.session.listen,
                    neighbor.session.md5_password,
                    neighbor.session.md5_base64,
                    neighbor.session.incoming_ttl,
                ):
                    log.critical(
                        lazymsg(
                            'startup.failed.listener ip={ip} port={port} neighbor={n}',
                            ip=neighbor.session.md5_ip,
                            port=neighbor.session.listen,
                            n=neighbor.name(),
                        ),
                        'reactor',
                    )
                    return self.Exit.listening

        # Start processes
        if not self.early_drop:
            self.processes.start(self.configuration.processes)

        # Drop privileges
        if not self.daemon.drop_privileges():
            log.critical(lazymsg('daemon.privileges.drop.failed user={u}', u=self.daemon.user), 'reactor')
            log.critical(lazymsg('daemon.privileges.help env=exabgp.daemon.user'), 'reactor')
            return self.Exit.privileges

        if self.early_drop:
            self.processes.start(self.configuration.processes)

        # Initialize logging with dropped privileges
        log.init(getenv())

        if not self.daemon.savepid():
            return self.Exit.pid

        # Setup async readers for API processes (after all processes are started)
        loop = asyncio.get_running_loop()
        self.processes.setup_async_readers(loop)
        log.debug(lazymsg('async.api.readers.configured'), 'reactor')

        # Wait for initial delay if configured
        wait = getenv().tcp.delay
        if wait:
            sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
            log.debug(lazymsg('reactor.waiting seconds={s}', s=sleeptime), 'reactor')
            await asyncio.sleep(float(sleeptime))

        # Run the async main event loop
        await self._async_main_loop()

        return self.exit_code

    def register_peer(self, name: str, peer: Peer) -> None:
        self._peers[name] = peer

    def teardown_peer(self, name: str, code: int) -> None:
        self._peers[name].teardown(code)

    def shutdown(self) -> None:
        """Terminate all the current BGP connections"""
        log.critical(lazymsg('reactor.shutdown'), 'reactor')
        if self.listener is not Listener.STOPPED:
            self.listener.stop()
            self.listener = Listener.STOPPED
        for key in self._peers.keys():
            self._peers[key].shutdown()
        self.asynchronous.clear()
        self.processes.terminate()
        self.daemon.removepid()
        self._stopping = True

    def reload(self) -> bool:
        """Reload the configuration and send to the peer the route which changed"""
        log.info(lazymsg('config.reload version={v}', v=version), 'configuration')

        reloaded = self.configuration.reload()

        if not reloaded:
            log.error(lazymsg('config.reload.failed'), 'configuration')
            log.error(lazymsg('config.reload.error error={e}', e=str(self.configuration.error)), 'configuration')
            return False

        for key, peer in self._peers.items():
            if key not in self.configuration.neighbors:
                log.debug(lazymsg('peer.removing name={name}', name=peer.neighbor.name()), 'reactor')
                peer.remove()

        for key, neighbor in self.configuration.neighbors.items():
            # new peer
            if key not in self._peers:
                log.debug(lazymsg('peer.adding name={name}', name=neighbor.name()), 'reactor')
                peer = Peer(neighbor, self)
                self._peers[key] = peer
            # modified peer
            elif self._peers[key].neighbor != neighbor:
                log.debug(lazymsg('peer.modified key={key} action=reestablish', key=key), 'reactor')
                self._peers[key].reestablish(neighbor)
            # same peer but perhaps not the routes
            else:
                # finding what route changed and sending the delta is not obvious
                log.debug(lazymsg('peer.unchanged key={key} action=reconfigure', key=key), 'reactor')
                self._peers[key].reconfigure(neighbor)
            for ip in self._ips:
                if ip.afi == neighbor.session.peer_address.afi:
                    self.listener.listen_on(
                        ip,
                        neighbor.session.peer_address,
                        self._port,
                        neighbor.session.md5_password,
                        neighbor.session.md5_base64,
                        None,
                    )
        log.info(lazymsg('config.loaded'), 'reactor')

        return True

    def restart(self) -> None:
        """Kill the BGP session and restart it"""
        log.info(lazymsg('reactor.restart version={v}', v=version), 'reactor')

        reloaded = self.configuration.reload()

        if reloaded is not True:
            # Configuration reload failed - do not proceed with stale/invalid config
            error_msg = reloaded if isinstance(reloaded, str) else 'unknown error'
            log.warning(lazymsg('config.reload.failed error={e}', e=error_msg), 'reactor')
            return

        for key in self._peers.keys():
            if key not in self.configuration.neighbors.keys():
                peer = self._peers[key]
                log.debug(lazymsg('peer.removing name={name}', name=peer.neighbor.name()), 'reactor')
                self._peers[key].remove()
            else:
                self._peers[key].reestablish()
        self.processes.start(self.configuration.processes, True)

    # def nexthops (self, peers):
    # 	return dict((peer,self._peers[peer].neighbor['local-address']) for peer in peers)
