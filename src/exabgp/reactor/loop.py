"""reactor/loop.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio  # noqa: F401 - Used by async event loop wrapper in Step 9
import errno
import re
import select
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Set

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.fsm import FSM
from exabgp.configuration.process import API_PREFIX
from exabgp.environment import getenv
from exabgp.logger import log, lazymsg
from exabgp.reactor.api import API
from exabgp.reactor.api.processes import ProcessError, Processes
from exabgp.reactor.asynchronous import ASYNC
from exabgp.reactor.daemon import Daemon
from exabgp.reactor.interrupt import Signal
from exabgp.reactor.listener import Listener
from exabgp.reactor.peer import ACTION, Peer
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
        self._ips: List[Any] = getenv().tcp.bind
        self._port: int = getenv().tcp.port
        self._stopping: bool = getenv().tcp.attempts > 0
        self.exit_code: int = self.Exit.unknown

        # Daemon identity for CLI health monitoring
        self.daemon_uuid: str = str(uuid.uuid4())
        self.daemon_start_time: float = time.time()

        # Active CLI client tracking (for multi-client replacement detection)
        self.active_client_uuid: str | None = None
        self.active_client_last_ping: float = 0.0

        self.max_loop_time: float = getenv().reactor.speed
        self._sleep_time: float = self.max_loop_time / 100
        self._busyspin: Dict[int, int] = {}
        self._ratelimit: Dict[str, Dict[int, int]] = {}
        self.early_drop: bool = getenv().daemon.drop

        self.processes: Processes

        self.configuration: Any = configuration
        self.asynchronous: ASYNC = ASYNC()
        self.signal: Signal = Signal()
        self.daemon: Daemon = Daemon(self)
        self.listener: Listener = Listener(self)
        self.api: API = API(self)

        self._peers: Dict[str, Peer] = {}

        self._saved_pid: bool = False
        self._poller: select.poll = select.poll()

    def _termination(self, reason: str, exit_code: int) -> None:
        self.exit_code = exit_code
        self.signal.received = Signal.SHUTDOWN
        log.critical(lambda: reason, 'reactor')

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
        ratelimit: Dict[int, int] = self._ratelimit.get(peer, {})
        if second not in ratelimit:
            self._ratelimit[peer] = {second: rate - 1}
            return False
        if self._ratelimit[peer][second] > 0:
            self._ratelimit[peer][second] -= 1
            return False
        return True

    def _wait_for_io(self, sleeptime: int) -> Generator[int, None, None]:
        spin_prevention = False
        try:
            for fd, event in self._poller.poll(sleeptime):
                if event & select.POLLIN or event & select.POLLPRI:
                    yield fd
                    continue
                elif event & select.POLLHUP or event & select.POLLERR or event & select.POLLNVAL:
                    spin_prevention = True
                    continue
            if spin_prevention:
                self._prevent_spin()
        except KeyboardInterrupt:
            self._termination('^C received', self.Exit.normal)
            return
        except OSError:
            self._prevent_spin()
            return

    async def _wait_for_io_async(self, sleeptime: int) -> list[int]:
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
            if self._rate_limited(key, peer.neighbor['rate-limit']):
                continue

            if not hasattr(peer, '_async_task') or peer._async_task is None:
                peer.start_async_task()

        # Wait briefly to allow tasks to run
        await asyncio.sleep(0)

        # Check for completed/failed peers
        completed_peers = []
        for key in list(self._peers.keys()):
            peer = self._peers[key]
            if hasattr(peer, '_async_task') and peer._async_task is not None:
                if peer._async_task.done():
                    try:
                        # Check if task raised an exception
                        peer._async_task.result()
                    except Exception as exc:
                        log.error(lazymsg('peer {key} task failed: {exc}', key=key, exc=exc), 'reactor')
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
        while True:
            try:
                # Handle signals
                if self.signal.received:
                    signaled = self.signal.received

                    # Report signal to peers
                    for key in self._peers:
                        if self._peers[key].neighbor.api['signal']:  # type: ignore[index]
                            self._peers[key].reactor.processes.signal(
                                self._peers[key].neighbor, Signal.name(self.signal.number)
                            )

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

    def active_peers(self) -> Set[str]:
        peers: Set[str] = set()
        for key, peer in self._peers.items():
            if peer.neighbor['passive'] and not peer.proto:
                continue
            peers.add(key)
        return peers

    def established_peers(self) -> Set[str]:
        peers: Set[str] = set()
        for key, peer in self._peers.items():
            if peer.fsm == FSM.ESTABLISHED:
                peers.add(key)
        return peers

    def peers(self, service: str = '') -> List[str]:
        matching: List[str] = []
        for peer_name, peer in self._peers.items():
            if service == '':
                matching.append(peer_name)
                continue
            if service.startswith(API_PREFIX):
                matching.append(peer_name)
                continue
            if service in peer.neighbor.api['processes']:  # type: ignore[index]
                matching.append(peer_name)
                continue
            if any(True for r in peer.neighbor.api['processes-match'] if re.match(r, service)):  # type: ignore[index]
                matching.append(peer_name)
                continue

        return matching

    def handle_connection(self, peer_name: str, connection: Any) -> Any:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for incoming connection', 'reactor')
            return None
        return peer.handle_connection(connection)

    def neighbor(self, peer_name: str) -> 'Neighbor' | None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for neighbor lookup', 'reactor')
            return None
        return peer.neighbor

    def neighbor_name(self, peer_name: str) -> str:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for name lookup', 'reactor')
            return ''
        return peer.neighbor.name()

    def neighbor_ip(self, peer_name: str) -> str:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for IP lookup', 'reactor')
            return ''
        return str(peer.neighbor['peer-address'])

    def neighbor_cli_data(self, peer_name: str) -> Dict[str, Any] | None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for CLI data', 'reactor')
            return None
        return peer.cli_data()

    def neighor_rib(self, peer_name: str, rib_name: str, advertised: bool = False) -> List[Any]:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for RIB lookup', 'reactor')
            return []
        families: List[Any] | None = None
        if advertised:
            families = peer.proto.negotiated.families if peer.proto else []
        rib = peer.neighbor.rib.outgoing if rib_name == 'out' else peer.neighbor.rib.incoming  # type: ignore[union-attr]
        return list(rib.cached_changes(families))

    def neighbor_rib_resend(self, peer_name: str) -> None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for RIB resend', 'reactor')
            return
        peer.resend(peer.neighbor['capability']['route-refresh'])

    def neighbor_rib_out_withdraw(self, peer_name: str) -> None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for outgoing withdraw', 'reactor')
            return
        peer.neighbor.rib.outgoing.withdraw()  # type: ignore[union-attr]

    def neighbor_rib_in_clear(self, peer_name: str) -> None:
        if not (peer := self._peers.get(peer_name, None)):
            log.critical(lambda: f'could not find peer {peer_name} for incoming clear', 'reactor')
            return
        peer.neighbor.rib.incoming.clear()  # type: ignore[union-attr]

    # ...

    def _pending_adjribout(self) -> bool:
        for peer in self.active_peers():
            if self._peers[peer].neighbor.rib.outgoing.pending():  # type: ignore[union-attr]
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

    def display(self, route: str, nlri_only: bool = False) -> bool:
        from exabgp.configuration.check import display_message, display_nlri

        if not self.reload():
            return False

        display = display_nlri if nlri_only else display_message

        neighbors = self.configuration.neighbors
        for neighbor in neighbors.values():
            if not display(neighbor, route):
                return False
        return True

    def run(self) -> int:
        # Check if legacy mode is enabled (default: asyncio)
        if not getenv().reactor.legacy:
            # Use asyncio event loop (default)
            return asyncio.run(self.run_async())

        # Use legacy generator-based event loop
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
            log.critical(
                lambda: f"could not drop privileges to '{self.daemon.user}' refusing to run as root", 'reactor'
            )
            log.critical(
                lambda: 'set the environmemnt value exabgp.daemon.user to change the unprivileged user', 'reactor'
            )
            return self.Exit.privileges

        if self.early_drop:
            self.processes.start(self.configuration.processes)

        # This is required to make sure we can write in the log location as we now have dropped root privileges
        log.init(getenv())  # type: ignore[arg-type]

        if not self.daemon.savepid():
            return self.Exit.pid

        wait = getenv().tcp.delay
        if wait:
            sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
            log.debug(lambda: f'waiting for {sleeptime} seconds before connecting', 'reactor')
            time.sleep(float(sleeptime))

        workers: dict = {}
        peers = set()
        api_fds: list = []
        ms_sleep = int(self._sleep_time * 1000)

        while True:
            try:
                if self.signal.received:
                    signaled = self.signal.received

                    # report that we received a signal
                    for key in self._peers:
                        if self._peers[key].neighbor.api['signal']:  # type: ignore[index]
                            self._peers[key].reactor.processes.signal(
                                self._peers[key].neighbor, Signal.name(self.signal.number)
                            )

                    self.signal.rearm()

                    # we always want to exit
                    if signaled == Signal.SHUTDOWN:
                        self.exit_code = self.Exit.normal
                        self.shutdown()
                        break

                    # it does mot matter what we did if we are restarting
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

                if self.listener.incoming():
                    # check all incoming connection
                    self.asynchronous.schedule(
                        str(uuid.uuid1()),
                        'checking for new connection(s)',
                        self.listener.new_connections(),
                    )

                sleep = ms_sleep

                # do not attempt to listen on closed sockets even if the peer is still here
                for io in list(workers.keys()):
                    if io == -1:
                        self._poller.unregister(io)
                        del workers[io]

                peers = self.active_peers()
                # give a turn to all the peers
                for key in list(peers):
                    peer = self._peers[key]

                    # limit the number of message handling per second
                    if self._rate_limited(key, peer.neighbor['rate-limit']):
                        peers.discard(key)
                        continue

                    # handle the peer
                    action = peer.run()

                    # .run() returns an ACTION enum:
                    # * immediate if it wants to be called again
                    # * later if it should be called again but has no work atm
                    # * close if it is finished and is closing down, or restarting
                    if action == ACTION.CLOSE:
                        if key in self._peers:
                            del self._peers[key]
                        peers.discard(key)
                    # we are loosing this peer, not point to schedule more process work
                    elif action == ACTION.LATER:
                        io = peer.socket()
                        if io != -1:
                            self._poller.register(
                                io,
                                select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLNVAL | select.POLLERR,
                            )
                            workers[io] = key
                        # no need to come back to it before a a full cycle
                        peers.discard(key)
                    elif action == ACTION.NOW:
                        sleep = 0

                    if not peers:
                        break

                # read at least on message per process if there is some and parse it
                for service, command in self.processes.received():
                    self.api.process(self, service, command)
                    sleep = 0

                self.asynchronous.run()

                if api_fds != self.processes.fds:
                    for fd in api_fds:
                        if fd == -1:
                            continue
                        if fd not in self.processes.fds:
                            self._poller.unregister(fd)
                    for fd in self.processes.fds:
                        if fd == -1:
                            continue
                        if fd not in api_fds:
                            self._poller.register(
                                fd,
                                select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLNVAL | select.POLLERR,
                            )
                    api_fds = self.processes.fds

                for io in self._wait_for_io(sleep):
                    if io not in api_fds:
                        peers.add(workers[io])

                if self._stopping and not self._peers.keys():
                    self._termination('exiting on peer termination', self.Exit.normal)

            except KeyboardInterrupt:
                self._termination('^C received', self.Exit.normal)
            except SystemExit:
                self._termination('exiting', self.Exit.normal)
            except OSError as exc:
                # Differentiate between different OS error types using errno
                if exc.errno == errno.EINTR:
                    # Interrupted system call, most likely ^C during I/O
                    self._termination('I/O Error received, most likely ^C during IO', self.Exit.io_error)
                elif exc.errno in (errno.EBADF, errno.EINVAL):
                    # Bad file descriptor or invalid argument - select() errors
                    self._termination('problem using select, stopping', self.Exit.select)
                else:
                    # Socket/network errors (ECONNRESET, EPIPE, ECONNREFUSED, etc.)
                    self._termination('socket error received', self.Exit.socket)
            except ProcessError:
                self._termination('Problem when sending message(s) to helper program, stopping', self.Exit.process)

        return self.exit_code

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

        # Start processes
        if not self.early_drop:
            self.processes.start(self.configuration.processes)

        # Drop privileges
        if not self.daemon.drop_privileges():
            log.critical(
                lambda: f"could not drop privileges to '{self.daemon.user}' refusing to run as root", 'reactor'
            )
            log.critical(
                lambda: 'set the environmemnt value exabgp.daemon.user to change the unprivileged user', 'reactor'
            )
            return self.Exit.privileges

        if self.early_drop:
            self.processes.start(self.configuration.processes)

        # Initialize logging with dropped privileges
        log.init(getenv())  # type: ignore[arg-type]

        if not self.daemon.savepid():
            return self.Exit.pid

        # Setup async readers for API processes (after all processes are started)
        loop = asyncio.get_running_loop()
        self.processes.setup_async_readers(loop)
        log.debug(lambda: '[ASYNC] API process readers configured', 'reactor')

        # Wait for initial delay if configured
        wait = getenv().tcp.delay
        if wait:
            sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
            log.debug(lambda: f'waiting for {sleeptime} seconds before connecting', 'reactor')
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
        log.critical(lambda: 'performing shutdown', 'reactor')
        if self.listener:
            self.listener.stop()
            self.listener = None  # type: ignore[assignment]
        for key in self._peers.keys():
            self._peers[key].shutdown()
        self.asynchronous.clear()
        self.processes.terminate()
        self.daemon.removepid()
        self._stopping = True

    def reload(self) -> bool:
        """Reload the configuration and send to the peer the route which changed"""
        log.info(lambda: f'performing reload of exabgp {version}', 'configuration')

        reloaded = self.configuration.reload()

        if not reloaded:
            log.error(lambda: 'could not load/reload configuration', 'configuration')
            log.error(lambda: str(self.configuration.error), 'configuration')
            return False

        for key, peer in self._peers.items():
            if key not in self.configuration.neighbors:
                log.debug(lazymsg('removing peer: {name}', name=peer.neighbor.name()), 'reactor')
                peer.remove()

        for key, neighbor in self.configuration.neighbors.items():
            # new peer
            if key not in self._peers:
                log.debug(lazymsg('new peer: {name}', name=neighbor.name()), 'reactor')
                peer = Peer(neighbor, self)
                self._peers[key] = peer
            # modified peer
            elif self._peers[key].neighbor != neighbor:
                log.debug(
                    lazymsg('peer definition change, establishing a new connection for {key}', key=key), 'reactor'
                )
                self._peers[key].reestablish(neighbor)
            # same peer but perhaps not the routes
            else:
                # finding what route changed and sending the delta is not obvious
                log.debug(
                    lazymsg('peer definition identical, updating peer routes if required for {key}', key=key), 'reactor'
                )
                self._peers[key].reconfigure(neighbor)
            for ip in self._ips:
                if ip.afi == neighbor['peer-address'].afi:
                    self.listener.listen_on(
                        ip,
                        neighbor['peer-address'],
                        self._port,
                        neighbor['md5-password'],
                        neighbor['md5-base64'],
                        None,
                    )
        log.info(lambda: 'loaded new configuration successfully', 'reactor')

        return True

    def restart(self) -> None:
        """Kill the BGP session and restart it"""
        log.info(lambda: f'performing restart of exabgp {version}', 'reactor')

        reloaded = self.configuration.reload()

        if reloaded is not True:
            # Configuration reload failed - do not proceed with stale/invalid config
            error_msg = reloaded if isinstance(reloaded, str) else 'unknown error'
            log.warning(lambda: f'configuration reload failed, keeping previous config: {error_msg}', 'reactor')
            return

        for key in self._peers.keys():
            if key not in self.configuration.neighbors.keys():
                peer = self._peers[key]
                log.debug(lazymsg('removing peer {name}', name=peer.neighbor.name()), 'reactor')
                self._peers[key].remove()
            else:
                self._peers[key].reestablish()
        self.processes.start(self.configuration.processes, True)

    # def nexthops (self, peers):
    # 	return dict((peer,self._peers[peer].neighbor['local-address']) for peer in peers)
