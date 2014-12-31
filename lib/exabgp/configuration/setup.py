# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2014-12-23.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.environment import environment
from exabgp.version import version

environment.application = 'exabgp'
environment.configuration = {
	'profile' : {
		'enable'        : (environment.boolean,environment.lower,'false',    'toggle profiling of the code'),
		'file'          : (environment.unquote,environment.quote,'',         'profiling result file, none means stdout, no overwriting'),
	},
	'pdb' : {
		'enable'        : (environment.boolean,environment.lower,'false',    'on program fault, start pdb the python interactive debugger'),
	},
	'daemon' : {
#		'identifier'    : (environment.unquote,environment.nop,'ExaBGP',     'a name for the log (to diferenciate multiple instances more easily)'),
		'pid'           : (environment.unquote,environment.quote,'',         'where to save the pid if we manage it'),
		'user'          : (environment.user,environment.quote,'nobody',      'user to run as'),
		'daemonize'     : (environment.boolean,environment.lower,'false',    'should we run in the background'),
	},
	'log' : {
		'enable'        : (environment.boolean,environment.lower,'true',     'enable logging'),
		'level'         : (environment.syslog_value,environment.syslog_name,'INFO', 'log message with at least the priority SYSLOG.<level>'),
		'destination'   : (environment.unquote,environment.quote,'stdout', 'where logging should log\n' \
		                  '                                  syslog (or no setting) sends the data to the local syslog syslog\n' \
		                  '                                  host:<location> sends the data to a remote syslog server\n' \
		                  '                                  stdout sends the data to stdout\n' \
		                  '                                  stderr sends the data to stderr\n' \
		                  '                                  <filename> send the data to a file' \
		),
		'all'           : (environment.boolean,environment.lower,'false',    'report debug information for everything'),
		'configuration' : (environment.boolean,environment.lower,'true',     'report command parsing'),
		'reactor'       : (environment.boolean,environment.lower,'true',     'report signal received, command reload'),
		'daemon'        : (environment.boolean,environment.lower,'true',     'report pid change, forking, ...'),
		'processes'     : (environment.boolean,environment.lower,'true',     'report handling of forked processes'),
		'network'       : (environment.boolean,environment.lower,'true',     'report networking information (TCP/IP, network state,...)'),
		'packets'       : (environment.boolean,environment.lower,'false',    'report BGP packets sent and received'),
		'rib'           : (environment.boolean,environment.lower,'false',    'report change in locally configured routes'),
		'message'       : (environment.boolean,environment.lower,'false',    'report changes in route announcement on config reload'),
		'timers'        : (environment.boolean,environment.lower,'false',    'report keepalives timers'),
		'routes'        : (environment.boolean,environment.lower,'false',    'report received routes'),
		'parser'        : (environment.boolean,environment.lower,'false',    'report BGP message parsing details'),
		'short'         : (environment.boolean,environment.lower,'false',    'use short log format (not prepended with time,level,pid and source)'),
	},
	'tcp' : {
		'once': (environment.boolean,environment.lower,'false', 'only one tcp connection attempt per peer (for debuging scripts)'),
		'delay': (environment.integer,environment.nop,'0',      'start to announce route when the minutes in the hours is a modulo of this number'),
		'bind': (environment.optional_ip,environment.quote,'', 'IP to bind on when listening (no ip to disable)'),
		'port': (environment.integer,environment.nop,'179', 'port to bind on when listening'),
		'acl': (environment.boolean,environment.lower,'', '(experimental) unimplemented'),
	},
	'bgp' : {
		'openwait': (environment.integer,environment.nop,'60','how many second we wait for an open once the TCP session is established'),
	},
	'cache' : {
		'attributes'  :  (environment.boolean,environment.lower,'true', 'cache all attributes (configuration and wire) for faster parsing'),
		'nexthops'    :  (environment.boolean,environment.lower,'true', 'cache routes next-hops (deprecated: next-hops are always cached)'),
	},
	'api' : {
		'encoder'  :  (environment.api,environment.lower,'text', '(experimental) default encoder to use with with external API (text or json)'),
		'highres'  :  (environment.boolean,environment.lower,'false','should we use highres timer in JSON'),
		'respawn'  :  (environment.boolean,environment.lower,'false','should we respawn a helper process if it dies'),
	},
	'reactor' : {
		'speed' : (environment.real,environment.nop,'1.0', 'time of one reactor loop\n'
		                                                   '%suse only if you understand the code.' % (' '* 34)),
	},
	# Here for internal use
	'internal' : {
		'name'    : (environment.nop,environment.nop,'ExaBGP', 'name'),
		'version' : (environment.nop,environment.nop,version,  'version'),
	},
	# Here for internal use
	'debug' : {
		'pdb' : (environment.boolean,environment.lower,'false','enable python debugger on errors'),
		'memory' : (environment.boolean,environment.lower,'false','command line option --memory'),
		'configuration' : (environment.boolean,environment.lower,'false','undocumented option: raise when parsing configuration errors'),
		'selfcheck' : (environment.boolean,environment.lower,'false','does a self check on the configuration file'),
		'route' : (environment.unquote,environment.quote,'','decode the route using the configuration'),
		'defensive' : (environment.boolean,environment.lower,'false', 'generate random fault in the code in purpose'),
		'rotate':  (environment.boolean,environment.lower,'false', 'rotate configurations file on reload (signal)'),
	},
}
