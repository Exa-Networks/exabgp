
"""
setup.py

Created by Thomas Mangin on 2014-12-23.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.environment import parsing
from exabgp.environment.environment import Env


_SPACE = ' ' * 33

LOGGING_HELP_STDOUT = f"""\
where logging should log
{_SPACE} syslog (or no setting) sends the data to the local syslog syslog
{_SPACE} host:<location> sends the data to a remote syslog server
{_SPACE} stdout sends the data to stdout
{_SPACE} stderr sends the data to stderr
{_SPACE} <filename> send the data to a file"""


CONFIGURATION = {
    'profile': {
        'enable': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'toggle profiling of the code',
        },
        'file': {
            'read': parsing.unquote,
            'write': parsing.quote,
            'value': '',
            'help': 'profiling result file, none means stdout, no overwriting',
        },
    },
    'pdb': {
        'enable': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'on program fault, start pdb the python interactive debugger',
        }
    },
    'daemon': {
        'pid': {
            'read': parsing.unquote,
            'write': parsing.quote,
            'value': '',
            'help': 'where to save the pid if we manage it',
        },
        'user': {
            'read': parsing.user,
            'write': parsing.quote,
            'value': 'nobody',
            'help': 'user to run the program as',
        },
        'daemonize': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'should we run in the background',
        },
        'drop': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'drop privileges before forking processes',
        },
        'umask': {
            'read': parsing.umask_read,
            'write': parsing.umask_write,
            'value': '0137',
            'help': 'run daemon with this umask, governs perms of logfiles etc.',
        },
    },
    'log': {
        'enable': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'enable logging to file or syslog',
        },
        'level': {
            'read': parsing.syslog_value,
            'write': parsing.syslog_name,
            'value': 'INFO',
            'help': 'log message with at least the priority SYSLOG.<level>',
        },
        'destination': {
            'read': parsing.unquote,
            'write': parsing.quote,
            'value': 'stdout',
            'help': LOGGING_HELP_STDOUT,
        },
        'all': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'report debug information for everything',
        },
        'configuration': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'report command parsing',
        },
        'reactor': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'report signal received, command reload',
        },
        'daemon': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'report pid change, forking, ...',
        },
        'processes': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'report handling of forked processes',
        },
        'network': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'report networking information (TCP/IP, network state,...)',
        },
        'statistics': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'report packet statistics',
        },
        'packets': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'report BGP packets sent and received',
        },
        'rib': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'report change in locally configured routes',
        },
        'message': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'report changes in route announcement on config reload',
        },
        'timers': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'report keepalives timers',
        },
        'routes': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'report received routes',
        },
        'parser': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'report BGP message parsing details',
        },
        'short': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'use short log format (not prepended with time,level,pid and source)',
        },
    },
    'tcp': {
        'once': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'only one tcp connection attempt per peer (for debuging scripts) - deprecated, use tcp.attempts',
        },
        'attempts': {
            'read': parsing.integer,
            'write': parsing.nop,
            'value': '0',
            'help': 'maximum tcp connection attempts per peer (0 for unlimited)',
        },
        'delay': {
            'read': parsing.integer,
            'write': parsing.nop,
            'value': '0',
            'help': 'start to announce route when the minutes in the hours is a modulo of this number',
        },
        'bind': {
            'read': parsing.ip_list,
            'write': parsing.quote_list,
            'value': '',
            'help': 'Space separated list of IPs to bind on when listening (no ip to disable)',
        },
        'port': {
            'read': parsing.integer,
            'write': parsing.nop,
            'value': '179',
            'help': 'port to bind on when listening',
        },
        'acl': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': '',
            'help': '(experimental please do not use) unimplemented',
        },
    },
    'bgp': {
        'passive': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'ignore the peer configuration and make all peers passive',
        },
        'openwait': {
            'read': parsing.integer,
            'write': parsing.nop,
            'value': '60',
            'help': 'how many seconds we wait for an open once the TCP session is established',
        },
    },
    'cache': {
        'attributes': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'cache all attributes (configuration and wire) for faster parsing',
        },
        'nexthops': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'cache routes next-hops (deprecated: next-hops are always cached)',
        },
    },
    'api': {
        'ack': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'acknowledge api command(s) and report issues',
        },
        'chunk': {
            'read': parsing.integer,
            'write': parsing.nop,
            'value': '1',
            'help': 'maximum lines to print before yielding in show routes api',
        },
        'encoder': {
            'read': parsing.api,
            'write': parsing.lower,
            'value': 'json',
            'help': '(experimental) default encoder to use with with external API (text or json)',
        },
        'compact': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'shorter JSON encoding for IPv4/IPv6 Unicast NLRI',
        },
        'respawn': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'should we try to respawn helper processes if they dies',
        },
        'terminate': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'should we terminate ExaBGP if any helper process dies',
        },
        'cli': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'true',
            'help': 'should we create a named pipe for the cli',
        },
        'pipename': {
            'read': parsing.unquote,
            'write': parsing.quote,
            'value': 'exabgp',
            'help': 'name to be used for the exabgp pipe',
        },
    },
    'reactor': {
        'speed': {
            'read': parsing.real,
            'write': parsing.nop,
            'value': '1.0',
            'help': f'reactor loop time\n{_SPACE} use only if you understand the code.',
        },
    },
    # Here for internal use
    'debug': {
        'pdb': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'enable python debugger on errors',
        },
        'memory': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'command line option --memory',
        },
        'configuration': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'undocumented option: raise when parsing configuration errors',
        },
        'selfcheck': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'does a self check on the configuration file',
        },
        'route': {
            'read': parsing.unquote,
            'write': parsing.quote,
            'value': '',
            'help': 'decode the route using the configuration',
        },
        'defensive': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'generate random fault in the code in purpose',
        },
        'rotate': {
            'read': parsing.boolean,
            'write': parsing.lower,
            'value': 'false',
            'help': 'rotate configurations file on reload (signal)',
        },
    },
}

# load the environment
Env.setup(CONFIGURATION)
