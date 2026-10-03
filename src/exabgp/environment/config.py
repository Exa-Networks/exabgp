"""config.py

Typed configuration system using dataclasses and descriptors.

Created by Thomas Mangin on 2024-11-29.
Copyright (c) 2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Generic, Iterator, TypeVar, cast, overload
import configparser as ConfigParser

from exabgp.environment import base
from exabgp.environment import parsing
from exabgp.protocol.ip import IP
from exabgp.util.mypyc import mypyc_attr

T = TypeVar('T')


class EnvironmentValueError(ValueError):
    """An environment variable or env file entry with a value its option refuses.

    The operator's mistake, not ours: main() reports it as one line and exits, without a traceback.
    """


# The configuration is read once at start-up, and relies on what a native compiled class
# does not do: ConfigOption is a generic dataclass used as a descriptor, the sections are
# walked with dir(), and Environment is a singleton made in __new__. So these stay ordinary
# Python classes when compiled (mypyc_attr native_class=False), their methods compiled.
@mypyc_attr(native_class=False)
@dataclass
class ConfigOption(Generic[T]):
    """Descriptor for typed configuration options."""

    default: T
    help: str
    reader: Callable[[str], T] | None = None
    writer: Callable[[T], str] | None = None

    name: str = field(default='', init=False)
    section: str = field(default='', init=False)

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        # Section name will be set when ConfigSection registers its options
        self.section = getattr(owner, '_section_name', '')

    @overload
    def __get__(self, obj: None, owner: type) -> ConfigOption[T]: ...

    @overload
    def __get__(self, obj: object, owner: type) -> T: ...

    def __get__(self, obj: object | None, owner: type) -> T | ConfigOption[T]:
        if obj is None:
            return self
        result: T = cast(Any, obj)._values.get(self.name, self.default)
        return result

    def __set__(self, obj: Any, value: T) -> None:
        obj._values[self.name] = value

    def parse(self, value: str) -> T:
        """Parse string value to typed value."""
        if self.reader is not None:
            return self.reader(value)
        # Infer parser from default type
        if isinstance(self.default, bool):
            return cast(T, parsing.boolean(value))
        if isinstance(self.default, int):
            return cast(T, parsing.integer(value))
        if isinstance(self.default, float):
            return cast(T, parsing.real(value))
        if isinstance(self.default, str):
            return cast(T, parsing.unquote(value))
        if isinstance(self.default, list):
            return cast(T, parsing.ip_list(value))
        raise TypeError(f'Unsupported config type: {type(self.default).__name__}')

    def format(self, value: T) -> str:
        """Format typed value to string for output."""
        if self.writer is not None:
            return self.writer(value)
        # Infer writer from default type
        if isinstance(self.default, bool):
            return parsing.lower(value)
        elif isinstance(self.default, str):
            return parsing.quote(value)
        elif isinstance(self.default, list):
            return parsing.quote_list(cast(list[Any], value))
        return str(value)


def option(
    default: T,
    help: str,
    reader: Callable[[str], T] | None = None,
    writer: Callable[[T], str] | None = None,
) -> ConfigOption[T]:
    """Factory for ConfigOption.

    A section declares each option as `name: ConfigOption[T] = option(...)`, and reads it as
    a T on an instance, through the descriptor. It was declared `name: T`, which the
    compiled build checks, and a ConfigOption is not a T.
    """
    return ConfigOption(default, help, reader, writer)


@mypyc_attr(native_class=False)
class ConfigSection:
    """Base class for typed configuration sections."""

    _section_name: ClassVar[str] = ''

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    @classmethod
    def options(cls) -> dict[str, ConfigOption[Any]]:
        """Return all ConfigOption descriptors."""
        result: dict[str, ConfigOption[Any]] = {}
        for name in dir(cls):
            attr = getattr(cls, name, None)
            if isinstance(attr, ConfigOption):
                result[name] = attr
        return result

    def __getitem__(self, key: str) -> Any:
        """Support dict-style access for backward compatibility."""
        key = key.replace('-', '_')
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Support dict-style assignment for backward compatibility."""
        key = key.replace('-', '_')
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for backward compatibility."""
        key = key.replace('-', '_')
        return key in self.options()

    def __iter__(self) -> Iterator[str]:
        """Support iteration over option names."""
        return iter(self.options().keys())

    def keys(self) -> Iterator[str]:
        """Return option names."""
        return iter(self.options().keys())

    def items(self) -> Iterator[tuple[str, Any]]:
        """Return (name, value) pairs."""
        for name in self.options():
            yield name, getattr(self, name)


# =============================================================================
# Typed Section Classes
# =============================================================================


@mypyc_attr(native_class=False)
class ProfileSection(ConfigSection):
    """Profile configuration section."""

    _section_name: ClassVar[str] = 'profile'

    enable: ConfigOption[bool] = option(False, 'toggle profiling of the code')
    file: ConfigOption[str] = option('', 'profiling result file, none means stdout, no overwriting')


@mypyc_attr(native_class=False)
class PdbSection(ConfigSection):
    """PDB configuration section."""

    _section_name: ClassVar[str] = 'pdb'

    enable: ConfigOption[bool] = option(False, 'on program fault, start pdb the python interactive debugger')


@mypyc_attr(native_class=False)
class DaemonSection(ConfigSection):
    """Daemon configuration section."""

    _section_name: ClassVar[str] = 'daemon'

    pid: ConfigOption[str] = option('', 'where to save the pid if we manage it')
    user: ConfigOption[str] = option('nobody', 'user to run the program as', reader=parsing.user)
    daemonize: ConfigOption[bool] = option(False, 'should we run in the background')
    drop: ConfigOption[bool] = option(True, 'drop privileges before forking processes')
    umask: ConfigOption[int] = option(
        0o137,
        'run daemon with this umask, governs perms of logfiles etc.',
        reader=parsing.umask_read,
        writer=parsing.umask_write,
    )


_SPACE: str = ' ' * 33
LOGGING_HELP_STDOUT: str = f"""\
where logging should log
{_SPACE} syslog (or no setting) sends the data to the local syslog syslog
{_SPACE} host:<location> sends the data to a remote syslog server
{_SPACE} stdout sends the data to stdout
{_SPACE} stderr sends the data to stderr
{_SPACE} <filename> send the data to a file"""


@mypyc_attr(native_class=False)
class LogSection(ConfigSection):
    """Log configuration section."""

    _section_name: ClassVar[str] = 'log'

    enable: ConfigOption[bool] = option(True, 'enable logging to file or syslog')
    level: ConfigOption[str] = option(
        'INFO',
        'log message with at least the priority SYSLOG.<level>',
        reader=parsing.syslog_value,
        writer=parsing.syslog_name,
    )
    destination: ConfigOption[str] = option('stdout', LOGGING_HELP_STDOUT)
    all: ConfigOption[bool] = option(False, 'report debug information for everything')
    configuration: ConfigOption[bool] = option(True, 'report command parsing')
    reactor: ConfigOption[bool] = option(True, 'report signal received, command reload')
    daemon: ConfigOption[bool] = option(True, 'report pid change, forking, ...')
    processes: ConfigOption[bool] = option(True, 'report handling of forked processes')
    network: ConfigOption[bool] = option(True, 'report networking information (TCP/IP, network state,...)')
    statistics: ConfigOption[bool] = option(True, 'report packet statistics')
    packets: ConfigOption[bool] = option(False, 'report BGP packets sent and received')
    rib: ConfigOption[bool] = option(False, 'report change in locally configured routes')
    message: ConfigOption[bool] = option(False, 'report changes in route announcement on config reload')
    timers: ConfigOption[bool] = option(False, 'report keepalives timers')
    routes: ConfigOption[bool] = option(False, 'report received routes')
    parser: ConfigOption[bool] = option(False, 'report BGP message parsing details')
    short: ConfigOption[bool] = option(True, 'use short log format (not prepended with time,level,pid and source)')


@mypyc_attr(native_class=False)
class TcpSection(ConfigSection):
    """TCP configuration section."""

    _section_name: ClassVar[str] = 'tcp'

    once: ConfigOption[bool] = option(
        False, 'only one tcp connection attempt per peer (for debuging scripts) - deprecated, use tcp.attempts'
    )
    attempts: ConfigOption[int] = option(0, 'maximum tcp connection attempts per peer (0 for unlimited)')
    delay: ConfigOption[int] = option(
        0, 'start to announce route when the minutes in the hours is a modulo of this number'
    )
    bind: ConfigOption[list[IP]] = option(
        [],
        'Space separated list of IPs to bind on when listening (no ip to disable)',
        reader=parsing.ip_list,
        writer=parsing.quote_list,
    )
    port: ConfigOption[int] = option(179, 'port to bind on when listening')
    acl: ConfigOption[bool] = option(False, '(experimental please do not use) unimplemented')


@mypyc_attr(native_class=False)
class BgpSection(ConfigSection):
    """BGP configuration section."""

    _section_name: ClassVar[str] = 'bgp'

    passive: ConfigOption[bool] = option(False, 'ignore the peer configuration and make all peers passive')
    openwait: ConfigOption[int] = option(60, 'how many seconds we wait for an open once the TCP session is established')
    paths_limit_audit: ConfigOption[bool] = option(
        True, 'log a warning when a peer sends more paths per prefix than our advertised PATHS-LIMIT'
    )


@mypyc_attr(native_class=False)
class CacheSection(ConfigSection):
    """Cache configuration section."""

    _section_name: ClassVar[str] = 'cache'

    attributes: ConfigOption[bool] = option(True, 'cache all attributes (configuration and wire) for faster parsing')
    nexthops: ConfigOption[bool] = option(True, 'cache routes next-hops (deprecated: next-hops are always cached)')


@mypyc_attr(native_class=False)
class ApiSection(ConfigSection):
    """API configuration section."""

    _section_name: ClassVar[str] = 'api'

    version: ConfigOption[int] = option(
        0,
        'API version of every helper: auto (0, detected for each from its commands), 4 (legacy) or 6',
        reader=parsing.api_version,
    )
    ack: ConfigOption[bool] = option(True, 'acknowledge api command(s) and report issues')
    chunk: ConfigOption[int] = option(1, 'maximum lines to print before yielding in show routes api')
    encoder: ConfigOption[str] = option(
        'json', 'default encoder for API v4 (text or json), ignored in v6', reader=parsing.api
    )
    compact: ConfigOption[bool] = option(False, 'shorter JSON encoding for IPv4/IPv6 Unicast NLRI')
    respawn: ConfigOption[bool] = option(True, 'should we try to respawn helper processes if they dies')
    terminate: ConfigOption[bool] = option(False, 'should we terminate ExaBGP if any helper process dies')
    cli: ConfigOption[bool] = option(True, 'should we create a named pipe for the cli')
    pipename: ConfigOption[str] = option('exabgp', 'name to be used for the exabgp pipe')
    socketname: ConfigOption[str] = option('exabgp', 'name to be used for the exabgp Unix socket')

    def __init__(self) -> None:
        super().__init__()
        # Store initial values for restoration when switching API versions
        # These are set by snapshot_initial() after config loading
        self._initial_version: int = 6  # Default until snapshot
        self._initial_encoder: str = 'json'  # Default until snapshot
        self._snapshot_done: bool = False

    def snapshot_initial(self) -> None:
        """Snapshot initial values (called once at startup after config load)."""
        if not self._snapshot_done:
            self._initial_version = self.version
            self._initial_encoder = self.encoder
            self._snapshot_done = True

    @property
    def initial_version(self) -> int:
        """Return initial API version (before any runtime changes)."""
        return self._initial_version

    @property
    def initial_encoder(self) -> str:
        """Return initial encoder setting (before any runtime changes)."""
        return self._initial_encoder


@mypyc_attr(native_class=False)
class ReactorSection(ConfigSection):
    """Reactor configuration section."""

    _section_name: ClassVar[str] = 'reactor'

    speed: ConfigOption[float] = option(1.0, f'reactor loop time\n{_SPACE} use only if you understand the code.')


@mypyc_attr(native_class=False)
class DebugSection(ConfigSection):
    """Debug configuration section."""

    _section_name: ClassVar[str] = 'debug'

    pdb: ConfigOption[bool] = option(False, 'enable python debugger on errors')
    memory: ConfigOption[bool] = option(False, 'command line option --memory')
    configuration: ConfigOption[bool] = option(False, 'undocumented option: raise when parsing configuration errors')
    selfcheck: ConfigOption[bool] = option(False, 'does a self check on the configuration file')
    route: ConfigOption[str] = option('', 'decode the route using the configuration')
    defensive: ConfigOption[bool] = option(False, 'generate random fault in the code in purpose')
    rotate: ConfigOption[bool] = option(False, 'rotate configurations file on reload (signal)')
    timing: ConfigOption[bool] = option(False, 'enable timing instrumentation for reactor performance analysis')


# =============================================================================
# Environment Class
# =============================================================================


nonedict: dict[str, str] = {}


@mypyc_attr(native_class=False)
class Environment:
    """Typed environment configuration singleton."""

    _instance: ClassVar[Environment | None] = None
    _setup_done: ClassVar[bool] = False

    # Typed section attributes
    profile: ProfileSection
    pdb: PdbSection
    daemon: DaemonSection
    log: LogSection
    tcp: TcpSection
    bgp: BgpSection
    cache: CacheSection
    api: ApiSection
    reactor: ReactorSection
    debug: DebugSection

    # The one environment of the process is Environment.instance(), made on first use. It
    # was made in __new__, with super().__new__(cls), which mypyc does not compile.
    @classmethod
    def instance(cls) -> Environment:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._init_sections()

    def _init_sections(self) -> None:
        """Initialize all configuration sections."""
        self.profile = ProfileSection()
        self.pdb = PdbSection()
        self.daemon = DaemonSection()
        self.log = LogSection()
        self.tcp = TcpSection()
        self.bgp = BgpSection()
        self.cache = CacheSection()
        self.api = ApiSection()
        self.reactor = ReactorSection()
        self.debug = DebugSection()

    def _sections(self) -> dict[str, ConfigSection]:
        """Return all sections as a dict."""
        return {
            'profile': self.profile,
            'pdb': self.pdb,
            'daemon': self.daemon,
            'log': self.log,
            'tcp': self.tcp,
            'bgp': self.bgp,
            'cache': self.cache,
            'api': self.api,
            'reactor': self.reactor,
            'debug': self.debug,
        }

    @classmethod
    def setup(cls) -> None:
        """Load configuration from environment variables and INI file."""
        if cls._setup_done:
            return
        cls._setup_done = True

        env = cls.instance()
        sections = env._sections()

        # Read INI file if exists
        # `key = value  # note`: without the prefixes the note is read as part of the value
        ini: ConfigParser.ConfigParser = ConfigParser.ConfigParser(inline_comment_prefixes=('#',))
        if os.path.exists(base.ENVFILE):
            ini.read(base.ENVFILE)

        # Load each section
        for section_name, section in sections.items():
            for option_name, opt in section.options().items():
                proxy_section = f'{base.APPLICATION}.{section_name}'
                env_name = f'{proxy_section}.{option_name}'
                rep_name = env_name.replace('.', '_')

                # Priority: env var (dot) > env var (underscore) > INI file > default
                conf: str | None = None
                if env_name in os.environ:
                    conf = os.environ.get(env_name)
                elif rep_name in os.environ:
                    conf = os.environ.get(rep_name)
                else:
                    try:
                        conf = parsing.unquote(ini.get(proxy_section, option_name, vars=nonedict))
                    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                        conf = None

                if conf is not None:
                    try:
                        section[option_name] = opt.parse(conf)
                    except (TypeError, ValueError) as exc:
                        raise EnvironmentValueError(f'invalid value {conf!r} for {env_name}: {exc}') from None

        # Backward compatibility for tcp.once -> tcp.attempts
        cls._handle_tcp_compatibility(env)

        # Snapshot initial API settings for restoration when switching versions
        env.api.snapshot_initial()

    @classmethod
    def _handle_tcp_compatibility(cls, env: Environment) -> None:
        """Handle backward compatibility for tcp configuration."""
        # Handle exabgp_tcp_connections as an alias for exabgp_tcp_attempts
        connections_env = os.environ.get('exabgp.tcp.connections') or os.environ.get('exabgp_tcp_connections')
        if connections_env:
            env.tcp.attempts = int(connections_env)

        # Backward compatibility: convert tcp.once to tcp.attempts if tcp.attempts not explicitly set
        once_env = os.environ.get('exabgp.tcp.once') or os.environ.get('exabgp_tcp_once')
        attempts_env = os.environ.get('exabgp.tcp.attempts') or os.environ.get('exabgp_tcp_attempts')

        # Only apply backward compatibility if tcp.attempts wasn't explicitly set
        if once_env and not attempts_env and not connections_env:
            if env.tcp.once:
                env.tcp.attempts = 1
            else:
                env.tcp.attempts = 0

    # =========================================================================
    # Backward compatibility with dict-like access
    # =========================================================================

    def __getitem__(self, key: str) -> ConfigSection:
        """Support dict-style access: env['api']"""
        key = key.replace('-', '_')
        result: ConfigSection = getattr(self, key)
        return result

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        key = key.replace('-', '_')
        attr = getattr(self, key, None)
        return attr is not None and isinstance(attr, ConfigSection)

    def __iter__(self) -> Iterator[str]:
        """Iterate over section names."""
        return iter(self._sections().keys())

    def keys(self) -> Iterator[str]:
        """Return section names."""
        return iter(self._sections().keys())

    def items(self) -> Iterator[tuple[str, ConfigSection]]:
        """Return (section_name, section) pairs."""
        return iter(self._sections().items())

    # =========================================================================
    # Output methods (for compatibility with old Env class)
    # =========================================================================

    @classmethod
    def default(cls) -> Iterator[str]:
        """Yield default configuration lines."""
        cls.setup()
        env = cls.instance()
        for section_name, section in env._sections().items():
            if section_name in ('internal', 'debug'):
                continue
            for option_name, opt in section.options().items():
                default = (
                    f"'{opt.default}'"
                    if opt.writer in (parsing.quote, parsing.syslog_name) or isinstance(opt.default, str)
                    else opt.default
                )
                yield f'{base.APPLICATION}.{section_name}.{option_name} {" " * (18 - len(section_name) - len(option_name))} {opt.help}. default ({default})'

    @classmethod
    def iter_ini(cls, diff: bool = False) -> Iterator[str]:
        """Yield INI-format configuration lines."""
        cls.setup()
        env = cls.instance()
        for section_name, section in env._sections().items():
            if section_name in ('internal', 'debug'):
                continue
            header = f'\n[{base.APPLICATION}.{section_name}]'
            for option_name, opt in section.options().items():
                value = getattr(section, option_name)
                if diff and value == opt.default:
                    continue
                if header:
                    yield header
                    header = ''
                yield f'{option_name} = {opt.format(value)}'

    @classmethod
    def iter_env(cls, diff: bool = False) -> Iterator[str]:
        """Yield environment variable format lines."""
        cls.setup()
        env = cls.instance()
        for section_name, section in env._sections().items():
            if section_name in ('internal', 'debug'):
                continue
            for option_name, opt in section.options().items():
                value = getattr(section, option_name)
                if diff and value == opt.default:
                    continue
                if opt.writer == parsing.quote or isinstance(opt.default, str):
                    yield f"{base.APPLICATION}.{section_name}.{option_name}='{value}'"
                else:
                    yield f'{base.APPLICATION}.{section_name}.{option_name}={opt.format(value)}'

    @classmethod
    def settings(cls) -> Environment:
        """Return the environment singleton (for backward compatibility)."""
        cls.setup()
        return cls.instance()
