#!/usr/bin/env python

"""Healthchecker for exabgp.

This program is to be used as a process for exabgp. It will announce
some VIP depending on the state of a check whose a third-party program
wrapped by this program.

To use, declare this program as a process in your
:file:`/etc/exabgp/exabgp.conf`::

    neighbor 192.0.2.1 {
       router-id 192.0.2.2;
       local-as 64496;
       peer-as 64497;
    }
    process watch-haproxy {
       run python -m exabgp healthcheck --cmd "curl -sf http://127.0.0.1/healthcheck" --label haproxy;
    }
    process watch-mysql {
       run python -m exabgp healthcheck --cmd "mysql -u check -e 'SELECT 1'" --label mysql;
    }

Use :option:`--help` to get options accepted by this program. A
configuration file is also possible. Such a configuration file looks
like this::

     debug
     name = haproxy
     interval = 10
     fast-interval = 1
     command = curl -sf http://127.0.0.1/healthcheck

The left-part of each line is the corresponding long option.

When using label for loopback selection, the provided value should
match the beginning of the label without the interface prefix. In the
example above, this means that you should have addresses on lo
labelled ``lo:haproxy1``, ``lo:haproxy2``, etc.

"""

from __future__ import print_function
from __future__ import unicode_literals

import sys
import os
import subprocess
import re
import logging
import logging.handlers
import argparse
import signal
import time
import collections

logger = logging.getLogger("healthcheck")

try:
    # Python 3.3+ or backport
    from ipaddress import ip_address as _ip_address  # pylint: disable=F0401

    def ip_address(x):
        try:
            x = x.decode('ascii')
        except AttributeError:
            pass
        return _ip_address(x)
except ImportError:
    try:
        # Python 2.6, 2.7, 3.2
        from ipaddr import IPAddress as ip_address
    except ImportError:
        sys.stderr.write(
            '\n'
            'This program requires the python module ip_address (for python 3.3+) or ipaddr (for python 2.6, 2.7, 3.2)\n'
            'Please pip install one of them with one of the following command.\n'
            '> pip install ip_address\n'
            '> pip install ipaddr\n'
            '\n'
        )
        sys.exit(1)

def enum(*sequential):
    """Create a simple enumeration."""
    return type(str("Enum"), (), dict(zip(sequential, sequential)))


def parse():
    """Parse arguments"""
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__,
                                     formatter_class=formatter)

    g = parser.add_mutually_exclusive_group()
    g.add_argument("--debug", "-d", action="store_true",
                   default=False,
                   help="enable debugging")
    g.add_argument("--silent", "-s", action="store_true",
                   default=False,
                   help="don't log to console")
    g.add_argument("--syslog-facility", "-sF", metavar="FACILITY",
                   nargs='?',
                   const="daemon",
                   default="daemon",
                   help=("log to syslog using FACILITY, "
                         "default FACILITY is daemon"))
    g.add_argument("--no-syslog", action="store_true",
                   help="disable syslog logging")
    parser.add_argument("--name", "-n", metavar="NAME",
                        help="name for this healthchecker")
    parser.add_argument("--config", "-F", metavar="FILE", type=open,
                        help="read configuration from a file")
    parser.add_argument("--pid", "-p", metavar="FILE",
                        type=argparse.FileType('w'),
                        help="write PID to the provided file")
    parser.add_argument("--user", metavar="USER",
                        help="set user after setting loopback addresses")
    parser.add_argument("--group", metavar="GROUP",
                        help="set group after setting loopback addresses")

    g = parser.add_argument_group("checking healthiness")
    g.add_argument("--interval", "-i", metavar='N',
                   default=5,
                   type=float,
                   help="wait N seconds between each healthcheck")
    g.add_argument("--fast-interval", "-f", metavar='N',
                   default=1,
                   type=float, dest="fast",
                   help=("when a state change is about to occur, "
                         "wait N seconds between each healthcheck"))
    g.add_argument("--timeout", "-t", metavar='N',
                   default=5,
                   type=int,
                   help="wait N seconds for the check command to execute")
    g.add_argument("--rise", metavar='N',
                   default=3,
                   type=int,
                   help="check N times before considering the service up")
    g.add_argument("--fall", metavar='N',
                   default=3,
                   type=int,
                   help="check N times before considering the service down")
    g.add_argument("--disable", metavar='FILE',
                   type=str,
                   help="if FILE exists, the service is considered disabled")
    g.add_argument("--command", "--cmd", "-c", metavar='CMD',
                   type=str,
                   help="command to use for healthcheck")

    g = parser.add_argument_group("advertising options")
    g.add_argument("--next-hop", "-N", metavar='IP',
                   type=ip_address,
                   help="self IP address to use as next hop")
    g.add_argument("--ip", metavar='IP',
                   type=ip_address, dest="ips", action="append",
                   help="advertise this IP address")
    g.add_argument("--no-ip-setup",
                   action="store_false", dest="ip_setup",
                   help="don't setup missing IP addresses")
    g.add_argument("--label", default=None,
                   help="use the provided label to match loopback addresses")
    g.add_argument("--start-ip", metavar='N',
                   type=int, default=0,
                   help="index of the first IP in the list of IP addresses")
    g.add_argument("--up-metric", metavar='M',
                   type=int, default=100,
                   help="first IP get the metric M when the service is up")
    g.add_argument("--down-metric", metavar='M',
                   type=int, default=1000,
                   help="first IP get the metric M when the service is down")
    g.add_argument("--disabled-metric", metavar='M',
                   type=int, default=500,
                   help=("first IP get the metric M "
                         "when the service is disabled"))
    g.add_argument("--increase", metavar='M',
                   type=int, default=1,
                   help=("for each additional IP address, "
                         "increase metric value by W"))
    g.add_argument("--community", metavar="COMMUNITY",
                   type=str, default=None,
                   help="announce IPs with the supplied community")
    g.add_argument("--as-path", metavar="ASPATH",
                   type=str, default=None,
                   help="announce IPs with the supplied as-path")
    g.add_argument("--withdraw-on-down", action="store_true",
                   help=("Instead of increasing the metric on health failure, "
                         "withdraw the route"))

    g = parser.add_argument_group("reporting")
    g.add_argument("--execute", metavar='CMD',
                   type=str, action="append",
                   help="execute CMD on state change")
    g.add_argument("--up-execute", metavar='CMD',
                   type=str, action="append",
                   help="execute CMD when the service becomes available")
    g.add_argument("--down-execute", metavar='CMD',
                   type=str, action="append",
                   help="execute CMD when the service becomes unavailable")
    g.add_argument("--disabled-execute", metavar='CMD',
                   type=str, action="append",
                   help="execute CMD when the service is disabled")

    options = parser.parse_args()
    if options.config is not None:
        # A configuration file has been provided. Read each line and
        # build an equivalent command line.
        args = sum(["--{0}".format(l.strip()).split("=", 1)
                    for l in options.config.readlines()
                    if not l.strip().startswith("#") and l.strip()], [])
        args = [x.strip() for x in args]
        args.extend(sys.argv[1:])
        options = parser.parse_args(args)
    return options


def setup_logging(debug, silent, name, syslog_facility, syslog):
    """Setup logger"""

    def syslog_address():
        """Return a sensitive syslog address"""
        if sys.platform == "darwin":
            return "/var/run/syslog"
        if sys.platform.startswith("freebsd"):
            return "/var/run/log"
        if sys.platform.startswith("linux"):
            return "/dev/log"
        raise EnvironmentError("Unable to guess syslog address for your "
                               "platform, try to disable syslog")

    logger.setLevel(debug and logging.DEBUG or logging.INFO)
    enable_syslog = syslog and not debug
    # To syslog
    if enable_syslog:
        facility = getattr(logging.handlers.SysLogHandler,
                           "LOG_{0}".format(syslog_facility.upper()))
        sh = logging.handlers.SysLogHandler(address=str(syslog_address()),
                                            facility=facility)
        if name:
            healthcheck_name = "healthcheck-{0}".format(name)
        else:
            healthcheck_name = "healthcheck"
        sh.setFormatter(logging.Formatter(
            "{0}[{1}]: %(message)s".format(
                healthcheck_name,
                os.getpid())))
        logger.addHandler(sh)
    # To console
    toconsole = (hasattr(sys.stderr, "isatty") and
                 sys.stderr.isatty() and  # pylint: disable=E1101
                 not silent)
    if toconsole:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            "%(levelname)s[%(name)s] %(message)s"))
        logger.addHandler(ch)


def loopback_ips(label):
    """Retrieve loopback IP addresses"""
    logger.debug("Retrieve loopback IP addresses")
    addresses = []

    if sys.platform.startswith("linux"):
        # Use "ip" (ifconfig is not able to see all addresses)
        ipre = re.compile(r"^(?P<index>\d+):\s+(?P<name>\S+)\s+inet6?\s+"
                          r"(?P<ip>[\da-f.:]+)/(?P<netmask>\d+)\s+.*")
        labelre = re.compile(r".*\s+lo:(?P<label>\S+).*")
        cmd = subprocess.Popen("/sbin/ip -o address show dev lo".split(),
                               shell=False, stdout=subprocess.PIPE)
    else:
        # Try with ifconfig
        ipre = re.compile(r"^inet6?\s+(alias\s+)?(?P<ip>[\da-f.:]+)\s+"
                          r"(?:netmask 0x(?P<netmask>[0-9a-f]+)|"
                          r"prefixlen (?P<mask>\d+)).*")
        cmd = subprocess.Popen("/sbin/ifconfig lo0".split(), shell=False,
                               stdout=subprocess.PIPE)
        labelre = re.compile(r"")
    for line in cmd.stdout:
        line = line.decode("ascii", "ignore").strip()
        mo = ipre.match(line)
        if not mo:
            continue
        ip = ip_address(mo.group("ip"))
        if not ip.is_loopback:
            if label:
                lmo = labelre.match(line)
                if not lmo or not lmo.group("label").startswith(label):
                    continue
            addresses.append(ip)
    logger.debug("Loopback addresses: %s", addresses)
    return addresses


def setup_ips(ips, label):
    """Setup missing IP on loopback interface"""
    existing = set(loopback_ips(label))
    toadd = set(ips) - existing
    for ip in toadd:
        logger.debug("Setup loopback IP address %s", ip)
        with open(os.devnull, "w") as fnull:
            cmd = ["ip", "address", "add", str(ip), "dev", "lo"]
            if label:
                cmd += ["label", "lo:{0}".format(label)]
            subprocess.check_call(
                cmd, stdout=fnull, stderr=fnull)

    # If we setup IPs we should also remove them on SIGTERM
    def sigterm_handler(signum, frame): # pylint: disable=W0612,W0613
        remove_ips(ips, label)

    signal.signal(signal.SIGTERM, sigterm_handler)


def remove_ips(ips, label):
    """Remove added IP on loopback interface"""
    existing = set(loopback_ips(label))

    # Get intersection of IPs (ips setup, and IPs configured by ExaBGP)
    toremove = set(ips) | existing
    for ip in toremove:
        logger.debug("Remove loopback IP address %s", ip)
        with open(os.devnull, "w") as fnull:
            # We specify the prefix length due to ip addr warnings about wildcard deletion
            cmd = ["ip", "address", "delete", str(ip) + "/32", "dev", "lo"]
            if label:
                cmd += ["label", "lo:{0}".format(label)]
            try:
                subprocess.check_call(
                    cmd, stdout=fnull, stderr=fnull)
            except subprocess.CalledProcessError:
                logger.warn("Unable to remove loopback IP address %s - is \
                    healthcheck running as root?", str(ip))
    sys.exit(0)


def drop_privileges(user, group):
    """Drop privileges to specified user and group"""
    if group is not None:
        import grp
        gid = grp.getgrnam(group).gr_gid
        logger.debug("Dropping privileges to group {0}/{1}".format(group, gid))
        try:
            os.setresgid(gid, gid, gid)
        except AttributeError:
            os.setregid(gid, gid)
    if user is not None:
        import pwd
        uid = pwd.getpwnam(user).pw_uid
        logger.debug("Dropping privileges to user {0}/{1}".format(user, uid))
        try:
            os.setresuid(uid, uid, uid)
        except AttributeError:
            os.setreuid(uid, uid)


def check(cmd, timeout):
    """Check the return code of the given command.

    :param cmd: command to execute. If :keyword:`None`, no command is executed.
    :param timeout: how much time we should wait for command completion.
    :return: :keyword:`True` if the command was successful or
             :keyword:`False` if not or if the timeout was triggered.
    """
    if cmd is None:
        return True

    class Alarm(Exception):
        """Exception to signal an alarm condition."""
        pass

    def alarm_handler(number, frame):  # pylint: disable=W0613
        """Handle SIGALRM signal."""
        raise Alarm()

    logger.debug("Checking command %s", repr(cmd))
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,
                         preexec_fn=os.setpgrp)
    if timeout:
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(timeout)
    try:
        stdout = None
        stdout, _ = p.communicate()
        if timeout:
            signal.alarm(0)
        if p.returncode != 0:
            logger.warn("Check command was unsuccessful: %s",
                        p.returncode)
            if stdout.strip():
                logger.info("Output of check command: %s", stdout)
            return False
        logger.debug(
            "Command was executed successfully %s %s", p.returncode, stdout)
        return True
    except Alarm:
        logger.warn("Timeout (%s) while running check command %s",
                    timeout, cmd)
        os.killpg(p.pid, signal.SIGKILL)
        return False


def loop(options):
    """Main loop."""
    states = enum(
        "INIT",                 # Initial state
        "DISABLED",             # Disabled state
        "RISING",               # Checks are currently succeeding.
        "FALLING",              # Checks are currently failing.
        "UP",                   # Service is considered as up.
        "DOWN",                 # Service is considered as down.
    )

    def exabgp(target):
        """Communicate new state to ExaBGP"""
        if target not in (states.UP, states.DOWN, states.DISABLED):
            return
        logger.info("send announces for %s state to ExaBGP", target)
        metric = vars(options).get("{0}_metric".format(str(target).lower()))
        for ip in options.ips:
            if options.withdraw_on_down:
                command = "announce" if target is states.UP else "withdraw"
            else:
                command = "announce"
            announce = "route {0}/{1} next-hop {2}".format(
                str(ip),
                ip.max_prefixlen,
                options.next_hop or "self")
            if command == "announce":
                announce = "{0} med {1}".format(announce, metric)
                if options.community:
                    announce = "{0} community [ {1} ]".format(
                        announce,
                        options.community)
                if options.as_path:
                    announce = "{0} as-path [ {1} ]".format(
                        announce,
                        options.as_path)
            logger.debug("exabgp: %s %s", command, announce)
            print("{0} {1}".format(command, announce))
            metric += options.increase
        sys.stdout.flush()

    def trigger(target):
        """Trigger a state change and execute the appropriate commands"""
        # Shortcut for RISING->UP and FALLING->UP
        if target == states.RISING and options.rise <= 1:
            target = states.UP
        elif target == states.FALLING and options.fall <= 1:
            target = states.DOWN

        # Log and execute commands
        logger.debug("Transition to %s", str(target))
        cmds = []
        cmds.extend(vars(options).get("{0}_execute".format(
            str(target).lower()), []) or [])
        cmds.extend(vars(options).get("execute", []) or [])
        for cmd in cmds:
            logger.debug("Transition to %s, execute `%s`",
                         str(target), cmd)
            env = os.environ.copy()
            env.update({"STATE": str(target)})
            with open(os.devnull, "w") as fnull:
                subprocess.call(
                    cmd, shell=True, stdout=fnull, stderr=fnull, env=env)

        return target

    def one(checks, state):
        """Execute one loop iteration."""
        disabled = (options.disable is not None and
                    os.path.exists(options.disable))
        successful = disabled or check(options.command, options.timeout)
        # FSM
        if state != states.DISABLED and disabled:
            state = trigger(states.DISABLED)
        elif state == states.INIT:
            if successful and options.rise <= 1:
                state = trigger(states.UP)
            elif successful:
                state = trigger(states.RISING)
                checks = 1
            else:
                state = trigger(states.FALLING)
                checks = 1
        elif state == states.DISABLED:
            if not disabled:
                state = trigger(states.INIT)
        elif state == states.RISING:
            if successful:
                checks += 1
                if checks >= options.rise:
                    state = trigger(states.UP)
            else:
                state = trigger(states.FALLING)
                checks = 1
        elif state == states.FALLING:
            if not successful:
                checks += 1
                if checks >= options.fall:
                    state = trigger(states.DOWN)
            else:
                state = trigger(states.RISING)
                checks = 1
        elif state == states.UP:
            if not successful:
                state = trigger(states.FALLING)
                checks = 1
        elif state == states.DOWN:
            if successful:
                state = trigger(states.RISING)
                checks = 1
        else:
            raise ValueError("Unhandled state: {0}".format(str(state)))

        # Send announces. We announce them on a regular basis in case
        # we lose connection with a peer.
        exabgp(state)
        return checks, state

    checks = 0
    state = states.INIT
    while True:
        checks, state = one(checks, state)

        # How much we should sleep?
        if state in (states.FALLING, states.RISING):
            time.sleep(options.fast)
        else:
            time.sleep(options.interval)


def main():
    """Entry point."""
    options = parse()
    setup_logging(options.debug, options.silent, options.name,
                  options.syslog_facility, not options.no_syslog)
    if options.pid:
        options.pid.write("{0}\n".format(os.getpid()))
        options.pid.close()
    try:
        # Setup IP to use
        options.ips = options.ips or loopback_ips(options.label)
        if not options.ips:
            logger.error("No IP found")
            sys.exit(1)
        if options.ip_setup:
            setup_ips(options.ips, options.label)
        drop_privileges(options.user, options.group)
        options.ips = collections.deque(options.ips)
        options.ips.rotate(-options.start_ip)
        options.ips = list(options.ips)
        # Main loop
        loop(options)
    except Exception as e:  # pylint: disable=W0703
        logger.exception("Uncaught exception: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
