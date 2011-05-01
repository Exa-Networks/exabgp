#!/bin/sh

# ignore Control C
# if the user ^C exabgp we will get that signal too, ignore it and let exabgp send us a SIGTERM
trap '' SIGINT

# command and watchdog name are case sensitive

while `true`;
do
echo "announce route 192.0.2.1 next-hop 10.0.0.1"
sleep 10
echo "withdraw route 192.0.2.1 next-hop 10.0.0.1"
sleep 15
done
