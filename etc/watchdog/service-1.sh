#!/bin/sh

# ignore Control C
trap '' 2

while `true`;
do
echo "announce watchdog watchdog-one"
sleep 5
echo "withdraw watchdog watchdog-one"
sleep 5
done
