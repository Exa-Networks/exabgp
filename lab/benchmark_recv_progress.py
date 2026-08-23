"""Cost of _recv_with_progress vs the bare await it replaced.

Same _reader_async, same socketpair, same data: only the helper is swapped.
Data-ready worst case: with bytes already buffered, the bare await completes
synchronously while ensure_future always pays a Task and a loop tick.
"""

import asyncio
import os
import socket
import statistics
import time

os.environ['exabgp_log_enable'] = 'false'

from exabgp.protocol.family import AFI
from exabgp.reactor.network.connection import Connection

MESSAGE_BYTES = 19
READS = 50_000
REPETITIONS = 5


class Bench(Connection):
    def __init__(self, sock: socket.socket) -> None:
        super().__init__(AFI.ipv4, '127.0.0.1', '127.0.0.1')
        self.io = sock
        self.established = True

    def name(self) -> str:
        return 'bench'

    def session(self) -> str:
        return 'bench'


async def bare_recv(self, view):  # the line the fix replaced
    loop = asyncio.get_event_loop()
    return await loop.sock_recv_into(self.io, view[self._read_offset_bytes :])


async def run_once(recv_method) -> float:
    ours, theirs = socket.socketpair()
    ours.setblocking(False)
    theirs.setblocking(False)
    connection = Bench(ours)
    original = Connection._recv_with_progress
    Connection._recv_with_progress = recv_method
    loop = asyncio.get_event_loop()

    async def feed() -> None:
        payload = b'\xff' * (MESSAGE_BYTES * 1000)
        for _ in range(READS // 1000):
            await loop.sock_sendall(theirs, payload)

    feeder = asyncio.ensure_future(feed())
    started = time.perf_counter()
    for _ in range(READS):
        await connection._reader_async(MESSAGE_BYTES)
    elapsed = time.perf_counter() - started
    await feeder
    Connection._recv_with_progress = original
    ours.close()
    theirs.close()
    return elapsed


async def main() -> None:
    for label, method in (
        ('bare await (old)', bare_recv),
        ('_recv_with_progress (new)', Connection._recv_with_progress),
    ):
        times = [await run_once(method) for _ in range(REPETITIONS)]
        median = statistics.median(times)
        print(
            f'{label:28} median {median:.3f}s  {READS / median:>9,.0f} reads/s  {median / READS * 1e6:6.2f} us/read  (runs: {" ".join(f"{t:.3f}" for t in times)})'
        )


asyncio.run(main())
