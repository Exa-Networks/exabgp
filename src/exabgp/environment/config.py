"""config.py

Typed configuration system using dataclasses and descriptors.

Created by Thomas Mangin on 2024-11-29.
Copyright (c) 2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar, ClassVar, Iterator, cast
import configparser as ConfigParser

from exabgp.environment import base
from exabgp.environment import parsing
from exabgp.environment.base import ENVFILE
from exabgp.protocol.ip import IP

T = TypeVar('T')


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

    def __get__(self, obj: Any, owner: type) -> T | ConfigOption[T]:
        if obj is None:
            return self
        result: T = obj._values.get(self.name, self.default)
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
) -> T:
    """Factory for ConfigOption - returns T for type inference."""
    return cast(T, ConfigOption(default, help, reader, writer))


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


class ProfileSection(ConfigSection):
    """Profile configuration section."""

    _section_name: ClassVar[str] = 'profile'

    enable: bool = option(False, 'toggle profiling of the code')
    file: str = option('', 'profiling result file, none means stdout, no overwriting')


class PdbSection(ConfigSection):
    """PDB configuration section."""

    _section_name: ClassVar[str] = 'pdb'

    enable: bool = option(False, 'on program fault, start pdb the python interactive debugger')


class DaemonSection(ConfigSection):
    """Daemon configuration section."""

    _section_name: ClassVar[str] = 'daemon'

    pid: str = option('', 'where to save the pid if we manage it')
    user: str = option('nobody', 'user to run the program as', reader=parsing.user)
    daemonize: bool = option(False, 'should we run in the background')
    drop: bool = option(True, 'drop privileges before forking processes')
    umask: int = option(
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


class LogSection(ConfigSection):
    """Log configuration section."""

    _section_name: ClassVar[str] = 'log'

    enable: bool = option(True, 'enable logging to file or syslog')
    level: str = option(
        'INFO',
        'log message with at least the priority SYSLOG.<level>',
        reader=parsing.syslog_value,
        writer=parsing.syslog_name,
    )
    destination: str = option('stdout', LOGGING_HELP_STDOUT)
    all: bool = option(False, 'report debug information for everything')
    configuration: bool = option(True, 'report command parsing')
    reactor: bool = option(True, 'report signal received, command reload')
    daemon: bool = option(True, 'report pid change, forking, ...')
    processes: bool = option(True, 'report handling of forked processes')
    network: bool = option(True, 'report networking information (TCP/IP, network state,...)')
    statistics: bool = option(True, 'report packet statistics')
    packets: bool = option(False, 'report BGP packets sent and received')
    rib: bool = option(False, 'report change in locally configured routes')
    message: bool = option(False, 'report changes in route announcement on config reload')
    timers: bool = option(False, 'report keepalives timers')
    routes: bool = option(False, 'report received routes')
    parser: bool = option(False, 'report BGP message parsing details')
    short: bool = option(True, 'use short log format (not prepended with time,level,pid and source)')


class TcpSection(ConfigSection):
    """TCP configuration section."""

    _section_name: ClassVar[str] = 'tcp'

    once: bool = option(
        False, 'only one tcp connection attempt per peer (for debuging scripts) - deprecated, use tcp.attempts'
    )
    attempts: int = option(0, 'maximum tcp connection attempts per peer (0 for unlimited)')
    delay: int = option(0, 'start to announce route when the minutes in the hours is a modulo of this number')
    bind: list[IP] = option(
        [],
        'Space separated list of IPs to bind on when listening (no ip to disable)',
        reader=parsing.ip_list,
        writer=parsing.quote_list,
    )
    port: int = option(179, 'port to bind on when listening')
    acl: bool = option(False, '(experimental please do not use) unimplemented')


class BgpSection(ConfigSection):
    """BGP configuration section."""

    _section_name: ClassVar[str] = 'bgp'

    passive: bool = option(False, 'ignore the peer configuration and make all peers passive')
    openwait: int = option(60, 'how many seconds we wait for an open once the TCP session is established')


class CacheSection(ConfigSection):
    """Cache configuration section."""

    _section_name: ClassVar[str] = 'cache'

    attributes: bool = option(True, 'cache all attributes (configuration and wire) for faster parsing')
    nexthops: bool = option(True, 'cache routes next-hops (deprecated: next-hops are always cached)')


class ApiSection(ConfigSection):
    """API configuration section."""

    _section_name: ClassVar[str] = 'api'

    ack: bool = option(True, 'acknowledge api command(s) and report issues')
    chunk: int = option(1, 'maximum lines to print before yielding in show routes api')
    encoder: str = option(
        'json', '(experimental) default encoder to use with with external API (text or json)', reader=parsing.api
    )
    compact: bool = option(False, 'shorter JSON encoding for IPv4/IPv6 Unicast NLRI')
    respawn: bool = option(True, 'should we try to respawn helper processes if they dies')
    terminate: bool = option(False, 'should we terminate ExaBGP if any helper process dies')
    cli: bool = option(True, 'should we create a named pipe for the cli')
    pipename: str = option('exabgp', 'name to be used for the exabgp pipe')
    socketname: str = option('exabgp', 'name to be used for the exabgp Unix socket')


class ReactorSection(ConfigSection):
    """Reactor configuration section."""

    _section_name: ClassVar[str] = 'reactor'

    speed: float = option(1.0, f'reactor loop time\n{_SPACE} use only if you understand the code.')
    legacy: bool = option(False, 'use legacy generator-based event loop instead of asyncio (default: asyncio)')


class DebugSection(ConfigSection):
    """Debug configuration section."""

    _section_name: ClassVar[str] = 'debug'

    pdb: bool = option(False, 'enable python debugger on errors')
    memory: bool = option(False, 'command line option --memory')
    configuration: bool = option(False, 'undocumented option: raise when parsing configuration errors')
    selfcheck: bool = option(False, 'does a self check on the configuration file')
    route: str = option('', 'decode the route using the configuration')
    defensive: bool = option(False, 'generate random fault in the code in purpose')
    rotate: bool = option(False, 'rotate configurations file on reload (signal)')


# =============================================================================
# Environment Class
# =============================================================================


nonedict: dict[str, str] = {}


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

    def __new__(cls) -> Environment:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_sections()
        return cls._instance

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

        env = cls()
        sections = env._sections()

        # Read INI file if exists
        ini: ConfigParser.ConfigParser = ConfigParser.ConfigParser()
        if os.path.exists(ENVFILE):
            ini.read(ENVFILE)

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
                    except TypeError:
                        raise ValueError(f'invalid value for {section_name}.{option_name} : {conf}') from None

        # Backward compatibility for tcp.once -> tcp.attempts
        cls._handle_tcp_compatibility(env)

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
        return hasattr(self, key) and isinstance(getattr(self, key), ConfigSection)

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
        env = cls()
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
        env = cls()
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
        env = cls()
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
        return cls()
