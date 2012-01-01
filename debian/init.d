#!/bin/sh
### BEGIN INIT INFO
# Provides:          exabgp
# Required-Start:    $network $local_fs $remote_fs
# Required-Stop:     $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: BGP route injector
# Description:       This program is a BGP route injector.
#  The route injector can connect using either IPv4 or IPv6 and announce both IPv4 and IPv6 routes.
#  Potential use are :
#  - Injection of service IPs like AS112 announcement
#  - Temporary route redirection (adding more specific routes with different next-hop)
#  - Injection of flow routes to handle DDOS
### END INIT INFO

# Author: Henry-Nicolas Tourneur <henry.nicolas@tourneur.be>

# PATH should only include /usr/* if it runs after the mountnfs.sh script
PATH=/sbin:/usr/sbin:/bin:/usr/bin
DESC="BGP route injector"
USER=exabgp
NAME=exabgp 
DAEMON=/usr/sbin/exabgp
DAEMON_ARGS="" 
PIDFILE=/var/run/$NAME/$NAME.pid
SCRIPTNAME=/etc/init.d/$NAME

# Exit if the package is not installed
[ -x $DAEMON ] || exit 0

# Some env var the daemon will need
export ETC="/etc/exabgp/"

# Read configuration variable file if it is present
[ -r /etc/default/$NAME ] && . /etc/default/$NAME

# Load the VERBOSE setting and other rcS variables
. /lib/init/vars.sh

# Define LSB log_* functions.
# Depend on lsb-base (>= 3.0-6) to ensure that this file is present.
. /lib/lsb/init-functions

if [ "$EXABGPRUN" = "no" ]; then
	log_daemon_msg "You need to set EXABGPRUN to yes in /etc/default/exabgp in order to use this daemon."
	log_end_msg 0
fi

#
# Function that starts the daemon/service
#
do_start()
{
        if [ "$EXABGPRUN" = "yes" ] || [ "$EXABGPRUN" = "YES" ]; then
		status_of_proc -p "$PIDFILE" "$DAEMON" "$NAME" > /dev/null 2>&1
                retcode=$?
                if [ $retcode -ne 0 ]; then
                        # Return
                        #   0 if daemon has been started
                        #   1 if daemon was already running
                        #   2 if daemon could not be started
			# We create the PID file and we do background thanks to start-stop-daemon
                        start-stop-daemon --start --quiet --pidfile $PIDFILE -c $USER -b -m --exec $DAEMON -- $DAEMON_OPTS || return 2
                else
                        log_daemon_msg "$NAME is already running!"
			log_end_msg 0
                        return 1
                fi
        fi
}

#
# Function that stops the daemon/service
#
do_stop()
{
	if [ "$EXABGPRUN" = "yes" ] || [ "$EXABGPRUN" = "YES" ]; then
		# Return
		#   0 if daemon has been stopped
		#   1 if daemon was already stopped
		#   2 if daemon could not be stopped
		#   other if a failure occurred
		start-stop-daemon --stop --quiet --signal TERM --pidfile $PIDFILE -c $USER
		RETVAL="$?"
		sleep 1
		# clean stale PID file
		rm $PIDFILE
		[ "$RETVAL" = 2 ] && return 2
		# Wait for children to finish too if this is a daemon that forks
		# and if the daemon is only ever run from this initscript.
		# If the above conditions are not satisfied then add some other code
		# that waits for the process to drop all resources that could be
		# needed by services started subsequently.  A last resort is to
		# sleep for some time.
		start-stop-daemon --stop --quiet --oknodo --retry=0/30/KILL/5 --exec $DAEMON
		[ "$?" = 2 ] && return 2
		sleep 1
		return "$RETVAL"
	fi
}

#
# Function that sends a SIGHUP to the daemon/service
#
do_reload() {
	if [ "$EXABGPRUN" = "yes" ] || [ "$EXABGPRUN" = "YES" ]; then
		start-stop-daemon --stop --signal HUP --quiet --pidfile $PIDFILE -c $USER
		return 0
	fi
}

case "$1" in
  start)
    log_daemon_msg "Starting $DESC " "$NAME"
    do_start
    case "$?" in
		0|1) log_end_msg 0 ;;
		2) log_end_msg 1 ;;
	esac
  ;;
  stop)
	log_daemon_msg "Stopping $DESC" "$NAME"
	do_stop
	case "$?" in
		0|1) log_end_msg 0 ;;
		2) log_end_msg 1 ;;
	esac
	;;
  status)
	status_of_proc -p "$PIDFILE" "$DAEMON" "$NAME" && exit 0 || exit $?
        ;;
  reload|force-reload)
	log_daemon_msg "Reloading $DESC" "$NAME"
	do_reload
	log_end_msg $?
	;;
  restart|force-reload)
	log_daemon_msg "Restarting $DESC" "$NAME"
	do_stop
	case "$?" in
	  0|1)
		do_start
		case "$?" in
			0) log_end_msg 0 ;;
			1) log_end_msg 1 ;; # Old process is still running
			*) log_end_msg 1 ;; # Failed to start
		esac
		;;
	  *)
	  	# Failed to stop
		log_end_msg 1
		;;
	esac
	;;
  *)
	echo "Usage: $SCRIPTNAME {start|stop|restart|reload|force-reload|status}" >&2
	exit 3
	;;
esac

exit 0
