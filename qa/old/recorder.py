"""What a 4.2 or 5.0 release makes of an API command, from its own code.

Run by qa/bin/record_old_commands with the Python and the source tree of that release on
PYTHONPATH (4.2: lib/, 5.0: src/). It is old code's view, so it is written for Python 3.10
and only uses what both releases have.

    python3.10 recorder.py grammar  < neighbor.conf               # the keyword tables
    python3.10 recorder.py record neighbor.conf < commands.json   # what each command does
    python3.10 recorder.py configurations < configurations.json   # what each configuration sends

`record` reads a JSON list of commands and prints, for each, whether the release accepts
it and the BGP messages it would send: the UPDATEs a route command makes, the End-of-RIB,
ROUTE-REFRESH or OPERATIONAL message of those commands, as hexadecimal. `configurations` reads
a JSON list of configurations and prints, for each, whether the release loads it and, for each
neighbor, the OPEN and the UPDATEs it sends once the session is up.
"""

import importlib
import inspect
import json
import pkgutil
import sys

# a command making more messages is recorded as accepted, without them
MAX_MESSAGES = 512


def _silence():
    try:
        from exabgp.environment import getenv  # 5.0
        from exabgp.logger import log
    except ImportError:
        from exabgp.configuration.setup import environment  # 4.2
        from exabgp.logger import Logger

        env = environment.setup('')
        env.log.enable = False
        # its failsafe format uses a time it never set when it has nowhere to write, and this
        # process writes its result on stdout: the logger is made to say nothing at all
        for level in ('debug', 'info', 'notice', 'warning', 'error', 'critical'):
            setattr(Logger, level, lambda self, *_, **__: None)
        Logger()
        return env
    env = getenv()
    log.silence()
    log.init(env)
    return env


def grammar():
    """Every keyword table of the configuration parser: section class -> keywords and syntax."""
    import exabgp.configuration as package

    found = {}
    for info in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        try:
            module = importlib.import_module(info.name)
        except Exception as exc:  # an optional module of the release, not ours to fix
            found[info.name] = {'error': repr(exc)}
            continue
        for name, kls in inspect.getmembers(module, inspect.isclass):
            known = getattr(kls, 'known', None)
            if kls.__module__ != module.__name__ or not isinstance(known, dict):
                continue
            found[f'{module.__name__}.{name}'] = {
                'name': getattr(kls, 'name', ''),
                # a key may be a tuple of words, `('rd', 'route-distinguisher')`: one keyword each
                'keywords': sorted({word for key in known for word in (key if isinstance(key, tuple) else (key,))}),
                'action': {str(key): str(value) for key, value in getattr(kls, 'action', {}).items()},
                'definition': list(getattr(kls, 'definition', [])),
            }
    return found


def _registered():
    from exabgp.reactor.api.command.command import Command

    functions = getattr(Command, 'functions', None)
    if functions is None:  # 4.2 keeps them per encoder
        functions = list(Command.callback['text'])
    return sorted(functions, key=len, reverse=True)


def _negotiated_42(neighbor, ibgp=True):
    """4.2 has no _negotiated: the session its check_neighbor builds, iBGP over the peer AS."""
    import copy

    from exabgp.bgp.message import Open
    from exabgp.bgp.message.open import ASN, HoldTime, RouterID, Version
    from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated

    neighbor = copy.deepcopy(neighbor)
    if ibgp:
        neighbor.local_as = neighbor.peer_as
    capa = Capabilities().new(neighbor, False)
    capa[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    peer_id = '.'.join(str((int(_) + 1) % 250) for _ in str(neighbor.router_id).split('.'))
    negotiated = Negotiated(neighbor)
    negotiated.sent(Open(Version(4), ASN(neighbor.local_as), HoldTime(180), RouterID(str(neighbor.router_id)), capa))
    negotiated.received(Open(Version(4), ASN(neighbor.peer_as), HoldTime(180), RouterID(peer_id), capa))
    return negotiated


def _session(configuration_file):
    """The neighbor the commands are for: its name, as the reactor lists it, and its session."""
    from exabgp.configuration.configuration import Configuration

    try:
        from exabgp.configuration.check import _negotiated  # 5.0
    except ImportError:
        _negotiated = _negotiated_42

    configuration = Configuration([configuration_file])
    if not configuration.reload():
        raise SystemExit(f'the neighbor configuration does not load: {configuration.error}')
    name, neighbor = list(configuration.neighbors.items())[0]
    return name, _negotiated(neighbor)


class Captured:
    """What the release's handler did: what it injected, and whether it answered an error."""

    def __init__(self):
        self.changes = []
        self.messages = []
        self.errors = 0


def _reactor(name, captured):
    """A reactor for the handler to run on, which records what the handler gives it."""
    from unittest.mock import MagicMock

    reactor = MagicMock()
    reactor.peers.return_value = [name]
    reactor.established_peers.return_value = [name]
    scheduled = []
    reactor.asynchronous.schedule.side_effect = lambda uid, command, callback: scheduled.append(callback)
    reactor.scheduled = scheduled

    def error(*_, **__):
        captured.errors += 1

    reactor.processes.answer_error.side_effect = error
    reactor.processes.answer.side_effect = lambda service, string, *_: error() if string == 'error' else None

    def inject(peers, change):
        # kept up to one past the cap: `split` hands the RIB millions of routes
        if len(captured.changes) <= MAX_MESSAGES:
            captured.changes.append(change)
        return True

    reactor.configuration.inject_change.side_effect = inject
    reactor.configuration.inject_eor.side_effect = lambda peers, family: captured.messages.append(('eor', family))
    reactor.configuration.inject_refresh.side_effect = lambda peers, refreshes: captured.messages.extend(
        ('refresh', refresh) for refresh in refreshes
    )
    reactor.configuration.inject_operational.side_effect = lambda peers, operational: captured.messages.append(
        ('operational', operational)
    )
    return reactor


def _run(callback):
    """Drive a scheduled callback, a generator, to its end."""
    if not hasattr(callback, '__next__'):
        return
    for _ in callback:
        pass


def _packed(captured, negotiated):
    from exabgp.bgp.message import Update

    messages = []
    for change in captured.changes:
        for message in Update([change.nlri], change.attributes).messages(negotiated):
            messages.append(message)
            if len(messages) > MAX_MESSAGES:
                break  # enough to know there are too many
        if len(messages) > MAX_MESSAGES:
            break
    for what, value in captured.messages:
        if what == 'eor':
            from exabgp.bgp.message.update.eor import EOR

            messages.append(EOR(value.afi, value.safi).message())
        elif what == 'refresh':
            messages.append(value.message())
        else:
            messages.append(value.message(negotiated))
    return [bytes(message).hex().upper() for message in messages]


def _matched(registered, command):
    """The registered command the release dispatches this one to, as its API.response does."""
    for name in registered:
        if name == command or command.endswith(' ' + name) or name + ' ' in command:
            return name
    return ''


def record(configuration_file, commands):
    """Each command through the release's own dispatcher and handler, and what it would send."""
    from exabgp.reactor.api import API

    name, negotiated = _session(configuration_file)
    registered = _registered()
    results = {}
    for command in commands:
        matched = _matched(registered, command)
        if not matched:
            results[command] = {'accepted': False, 'why': 'not a command'}
            continue
        captured = Captured()
        reactor = _reactor(name, captured)
        api = API(reactor)
        try:
            (getattr(api, 'process', None) or api.text)(reactor, 'helper', command)  # 5.0, or 4.2
            for callback in reactor.scheduled:
                _run(callback)
            messages = _packed(captured, negotiated)
        except Exception as exc:
            if not matched.startswith(('announce', 'withdraw')):
                # show, teardown, flush, ...: dispatched is what there is to know, and what
                # their handler does next needs a reactor this stand-in is not
                results[command] = {'accepted': True, 'command': matched, 'messages': []}
                continue
            # the release raised on it: what it does with a helper's typo
            results[command] = {'accepted': False, 'why': f'{type(exc).__name__}: {exc}'}
            continue
        if captured.errors:
            results[command] = {'accepted': False, 'why': f'{matched} answered error'}
            continue
        if len(messages) > MAX_MESSAGES:
            # `split /32` of a /8 is sixteen million UPDATEs: true, and nothing a check can hold
            results[command] = {'accepted': True, 'command': matched, 'too_many': f'over {MAX_MESSAGES}'}
            continue
        results[command] = {'accepted': True, 'command': matched, 'messages': messages}
    return results


def _open(neighbor):
    """The OPEN the release sends this neighbor, as its Protocol.new_open builds it."""
    from exabgp.bgp.message import Open
    from exabgp.bgp.message.open import Version
    from exabgp.bgp.message.open.capability import Capabilities

    if hasattr(neighbor, 'local_as'):  # 4.2
        capabilities = Capabilities().new(neighbor, False)
        return Open(Version(4), neighbor.local_as, neighbor.hold_time, neighbor.router_id, capabilities)
    local_as = neighbor['local-as'] or neighbor['peer-as']
    capabilities = Capabilities().new(neighbor, False, local_as=local_as)
    return Open(Version(4), local_as, neighbor['hold-time'], neighbor['router-id'], capabilities)


def _session_of(neighbor):
    """The session of this neighbor as configured, not made iBGP: eBGP changes what is sent."""
    try:
        from exabgp.configuration.check import _negotiated  # 5.0
    except ImportError:
        return _negotiated_42(neighbor, ibgp=False)
    return _negotiated(neighbor)


def _sent(neighbor):
    """The OPEN and the UPDATEs the release sends a neighbor once the session is up."""
    found = {'open': bytes(_open(neighbor).message()).hex().upper(), 'updates': []}
    negotiated = _session_of(neighbor)
    for update in neighbor.rib.outgoing.updates(False):
        if not hasattr(update, 'messages'):
            continue  # a route refresh marker, there is none on a first session
        for message in update.messages(negotiated):
            found['updates'].append(bytes(message).hex().upper())
            if len(found['updates']) > MAX_MESSAGES:
                found['too_many'] = f'over {MAX_MESSAGES}'
                found['updates'] = []
                return found
    return found


# a configuration with more neighbors is recorded for the first ones only
MAX_NEIGHBORS = 8


def record_configurations(configurations):
    """Each configuration loaded by the release, and what it sends each of its neighbors."""
    from exabgp.configuration.configuration import Configuration
    from exabgp.rib import RIB

    results = {}
    for text in configurations:
        # a RIB outlives a reload by its neighbor's name: each configuration starts with none
        RIB._cache.clear()
        with open('recorded.conf', 'w') as handle:
            handle.write(text)
        try:
            configuration = Configuration(['recorded.conf'])
            loaded = configuration.reload()
        except Exception as exc:
            results[text] = {'accepted': False, 'why': f'{type(exc).__name__}: {exc}'}
            continue
        if not loaded:
            results[text] = {'accepted': False, 'why': str(configuration.error)}
            continue
        neighbors = {}
        for name, neighbor in list(configuration.neighbors.items())[:MAX_NEIGHBORS]:
            try:
                neighbors[name] = _sent(neighbor)
            except Exception as exc:  # accepted, and can not be sent: the release's own bug
                neighbors[name] = {'error': f'{type(exc).__name__}: {exc}'}
        results[text] = {'accepted': True, 'neighbors': neighbors}
    return results


def main():
    _silence()
    if sys.argv[1] == 'grammar':
        json.dump({'registered': _registered(), 'sections': grammar()}, sys.stdout, indent=1, sort_keys=True)
        return
    if sys.argv[1] == 'configurations':
        json.dump(record_configurations(json.load(sys.stdin)), sys.stdout, indent=1, sort_keys=True)
        return
    json.dump(record(sys.argv[2], json.load(sys.stdin)), sys.stdout, indent=1, sort_keys=True)


if __name__ == '__main__':
    main()
