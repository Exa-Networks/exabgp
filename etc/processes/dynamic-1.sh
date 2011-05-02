#!/bin/sh

# ignore Control C
# if the user ^C exabgp we will get that signal too, ignore it and let exabgp send us a SIGTERM
trap '' SIGINT

# command and watchdog name are case sensitive

while `true`;
do
echo "announce flow route {\\\\n match {\\\\n source 10.0.0.1/32;\\\\n destination 1.2.3.4/32;\\\\n }\\\\n then {\\\\n discard;\\\\n }\\\\n }\\\\n"
sleep 10
echo "announce route 192.0.2.1 next-hop 10.0.0.1"
sleep 10
echo "withdraw route 192.0.2.1 next-hop 10.0.0.1"
sleep 10
echo "withdraw flow route {\\\\n match {\\\\n source 10.0.0.1/32;\\\\n destination 1.2.3.4/32;\\\\n }\\\\n then {\\\\n discard;\\\\n }\\\\n }\\\\n"
sleep 10
done
