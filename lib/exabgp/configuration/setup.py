# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2014-12-23.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.environment import environment

_SPACE = {
	'space':  ' '*33
}

HELP_STDOUT = """\
where logging should log
%(space)s syslog (or no setting) sends the data to the local syslog syslog
%(space)s host:<location> sends the data to a remote syslog server
%(space)s stdout sends the data to stdout
%(space)s stderr sends the data to stderr
%(space)s <filename> send the data to a file""" % _SPACE


environment.application = 'exabgp'
environment.configuration = {
	'profile':  {
		'enable':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'toggle profiling of the code',
		},
		'file':  {
			'read':  environment.unquote,
			'write': environment.quote,
			'value': '',
			'help':  'profiling result file, none means stdout, no overwriting',
		},
	},
	'pdb':  {
		'enable':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'on program fault, start pdb the python interactive debugger',
		}
	},
	'daemon':  {
		'pid':  {
			'read':  environment.unquote,
			'write': environment.quote,
			'value': '',
			'help':  'where to save the pid if we manage it',
		},
		'user':  {
			'read':  environment.user,
			'write': environment.quote,
			'value': 'nobody',
			'help':  'user to run as',
		},
		'daemonize':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'should we run in the background',
		},
		'drop':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'drop privileges before forking processes',
		},
	},
	'log':  {
		'enable':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'enable logging',
		},
		'level':  {
			'read':  environment.syslog_value,
			'write': environment.syslog_name,
			'value': 'INFO',
			'help':  'log message with at least the priority SYSLOG.<level>',
		},
		'destination':  {
			'read':  environment.unquote,
			'write': environment.quote,
			'value': 'stdout',
			'help':  HELP_STDOUT,
		},
		'all':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report debug information for everything',
		},
		'configuration':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report command parsing',
		},
		'reactor':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report signal received, command reload',
		},
		'daemon':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report pid change, forking, ...',
		},
		'processes':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report handling of forked processes',
		},
		'network':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report networking information (TCP/IP, network state,...)',
		},
		'packets':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report BGP packets sent and received',
		},
		'rib':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report change in locally configured routes',
		},
		'message':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report changes in route announcement on config reload',
		},
		'timers':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report keepalives timers',
		},
		'routes':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report received routes',
		},
		'parser':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report BGP message parsing details',
		},
		'short':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'use short log format (not prepended with time,level,pid and source)',
		},
	},
	'tcp':  {
		'once': {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'only one tcp connection attempt per peer (for debuging scripts)',
		},
		'delay': {
			'read':  environment.integer,
			'write': environment.nop,
			'value': '0',
			'help':  'start to announce route when the minutes in the hours is a modulo of this number',
		},
		'bind': {
			'read':  environment.optional_ip,
			'write': environment.quote,
			'value': '',
			'help':  'IP to bind on when listening (no ip to disable)',
		},
		'port': {
			'read':  environment.integer,
			'write': environment.nop,
			'value': '179',
			'help':  'port to bind on when listening',
		},
		'acl': {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': '',
			'help':  '(experimental) unimplemented',
		},
	},
	'bgp':  {
		'openwait': {
			'read':  environment.integer,
			'write': environment.nop,
			'value': '60',
			'help':  'how many second we wait for an open once the TCP session is established',
		},
	},
	'cache':  {
		'attributes':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'cache all attributes (configuration and wire) for faster parsing',
		},
		'nexthops':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'cache routes next-hops (deprecated: next-hops are always cached)',
		},
	},
	'api':  {
		'encoder':  {
			'read':  environment.api,
			'write': environment.lower,
			'value': 'text',
			'help':  '(experimental) default encoder to use with with external API (text or json)',
		},
		'highres':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'should we use highres timer in JSON',
		},
		'respawn':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'should we respawn a helper process if it dies',
		},
		'socket':  {
			'read':  environment.unquote,
			'write': environment.quote,
			'value': '',
			'help':  'where should we create a socket for remote control',
		},
	},
	'reactor':  {
		'speed':  {
			'read':  environment.real,
			'write': environment.nop,
			'value': '1.0',
			'help':  'reactor loop time\n%(space)s use only if you understand the code.' % _SPACE,
		},
	},
	# Here for internal use
	'debug':  {
		'pdb':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'enable python debugger on errors',
		},
		'memory':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'command line option --memory',
		},
		'configuration':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'undocumented option: raise when parsing configuration errors',
		},
		'selfcheck':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'does a self check on the configuration file',
		},
		'route':  {
			'read':  environment.unquote,
			'write': environment.quote,
			'value': '',
			'help':  'decode the route using the configuration',
		},
		'defensive':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'generate random fault in the code in purpose',
		},
		'rotate': {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'rotate configurations file on reload (signal)',
		},
	},
}
