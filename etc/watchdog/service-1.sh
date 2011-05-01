#!/bin/sh

# ignore Control C
# if the user ^C exabgp we will get that signal too, ignore it and let exabgp send us a SIGTERM
trap '' SIGINT

# command and watchdog name are case sensitive

while `true`;
do

# Let give exabgp the time to setup the BGP session :)
# But we do not have too, exabgp will record the changes and update the routes once up otherwise

sleep 10

# without name exabgp will use the name of the service as watchdog name
echo "withdraw watchdog"
sleep 5

# specify a watchdog name (which may be the same or different each time)
echo "withdraw watchdog watchdog-one"
sleep 5

echo "announce watchdog"
sleep 5

echo "announce watchdog watchdog-one"
sleep 5

# we have no route with that watchdog but it does not matter, we could have after a configuration reload

echo "announce watchdog watchdog-two"
echo "withdraw watchdog watchdog-two"

done
