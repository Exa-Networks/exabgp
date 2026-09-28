"""A reload which fails leaves the configuration as it was, its processes included.

After every reload the reactor gives Processes.start() the processes of the configuration,
and start() stops each running process which is not in it. A failed reload left the
configuration with the processes of the part read before the error (legacy parser), or with
none (grammar): a mistake in the file, and a SIGHUP, stopped the API programs.
"""

from __future__ import annotations

from exabgp.configuration.configuration import Configuration

VALID = """\
process watcher {
    run /bin/cat;
    encoder json;
}
neighbor 127.0.0.1 {
    router-id 10.0.0.1;
    local-address 127.0.0.1;
    local-as 65001;
    peer-as 65002;
    api { processes [ watcher ]; }
}
"""


def test_a_failed_reload_keeps_the_processes_and_the_neighbors(tmp_path) -> None:
    path = tmp_path / 'exabgp.conf'
    path.write_text(VALID)
    configuration = Configuration([str(path)])
    assert configuration.reload(), str(configuration.error)
    processes = dict(configuration.processes)
    neighbors = dict(configuration.neighbors)
    assert 'watcher' in processes

    path.write_text(VALID.replace('encoder json;', 'encoder jsn;'))
    assert not configuration.reload()

    assert configuration.processes == processes
    assert configuration.neighbors == neighbors
    assert 'jsn' in str(configuration.error)
