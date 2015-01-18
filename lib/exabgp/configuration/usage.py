# encoding: utf-8
"""
usage.py

Created by Thomas Mangin on 2014-12-19.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

usage = """\
The BGP swiss army knife of networking

usage: exabgp [--help] [--version] [--folder FOLDER] [--env ENV]
              [[--full-ini | --diff-ini | --full-env | --diff-env] |
              [--fi | --di | --fe | --de]]
              [--debug] [--pdb] [--test]
              [--once] [--signal TIME]
              [--memory] [--profile PROFILE]
              [--decode HEX_MESSAGE]...
              [<configuration>...]

positional arguments:
  configuration         peer and route configuration file

optional arguments:
  --help, -h            exabgp manual page
  --version, -v         shows ExaBGP version
  --folder FOLDER, -f FOLDER
                        configuration folder
  --env ENV, -e ENV     environment configuration file
  --full-ini            display the configuration using the ini format
  --fi                  (shorthand for above)
  --diff-ini            display non-default configurations values using the ini
                        format
  --di                  (shorthand for above)
  --full-env            display the configuration using the env format
  --fe                  (shorthand for above)
  --diff-env            display non-default configurations values using the env
                        format
  --de                  (shorthand for above)

debugging:
  --debug, -d           start the python debugger on serious logging and on
                        SIGTERM (shortcut for exabgp.log.all=true
                        exabgp.log.level=DEBUG)
  --signal TIME         issue a SIGUSR1 to reload the configuraiton after
                        <time> seconds, only useful for code debugging
  --once, -1            only perform one attempt to connect to peers (used for
                        debugging)
  --pdb, -p             fire the debugger on critical logging, SIGTERM, and
                        exceptions (shortcut for exabgp.pdb.enable=true)
  --memory, -s          display memory usage information on exit
  --profile PROFILE     enable profiling (shortcut for
                        exabgp.profile.enable=true exabgp.profile.file=PROFILE)
  --test, -t            perform a configuration validity check only
  --decode HEX_MESSAGE, -x HEX_MESSAGE
                        decode a raw route packet in hexadecimal string


ExaBGP will automatically look for its configuration file (in windows ini
format):
 * in the etc/exabgp folder located within the extracted tar.gz
 * in /etc/exabgp/exabgp.env

Individual configuration options can be set using environment variables, such
as:
 > env exabgp.daemon.daemonize=true ./sbin/exabgp
or:
 > env exabgp.daemon.daemonize=true ./sbin/exabgp
or:
 > export exabgp.daemon.daemonize=true; ./sbin/exabgp

Multiple environment values can be set, the order of preference being:
 1) command line environment value using dot separated notation
 2) exported value from the shell using dot separated notation
 3) command line environment value using underscore separated notation
 4) exported value from the shell using underscore separated notation
 5) the value in the ini configuration file
 6) the built-in defaults

For example :
 > env exabgp.profile.enable=true \\
      exabgp.profile.file=~/profile.log  \\
      exabgp.log.packets=true \\
      exabgp.log.destination=host:127.0.0.1 \\
      exabgp.daemon.user=wheel \\
      exabgp.daemon.daemonize=true \\
      exabgp.daemon.pid=/var/run/exabpg.pid \\
 > ./bin/exabgp ./etc/bgp/configuration.txt

The program configuration can be controlled using signals:
 * SIGLARM : restart ExaBGP
 * SIGUSR1 : reload the configuration
 * SIGUSR2 : reload the configuration and the forked processes
 * SIGTERM : terminate ExaBGP
 * SIGHUP  : terminate ExaBGP (does NOT reload the configuration anymore)
"""
