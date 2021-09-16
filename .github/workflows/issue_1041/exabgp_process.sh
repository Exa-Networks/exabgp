#!/bin/bash

# Let BGP to come up and "peer" to announce its routes.
sleep 5

echo "neighbor 10.0.1.3 announce route 2001:db8:1::/48 next-hop aa:bb:cc:dd::2 as-path [65510] community [no-export no-advertise]"
sleep 2

echo "neighbor 10.0.1.3 withdraw route 2001:db8:1::/48"
sleep 2

echo "Sleeping a lot..."
sleep 99999
