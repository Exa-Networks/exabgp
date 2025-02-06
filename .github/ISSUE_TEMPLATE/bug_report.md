---
name: Bug report
about: Create a report to help us improve
title: ''
labels: bug
assignees: ''

---

We are sorry to hear that you are experiencing an issue with ExaBGP.

Before opening this issue could you please:
 - check if the problem is still present on main branch
 - make sure the problem was not already reported to avoid duplicates.

# Common issues

If the program is freezing/stop responding, please look at our convertion from 3.4 to 4.x, please look at https://github.com/Exa-Networks/exabgp/wiki/Migration-from-3.4-to-4.x#api for more information.

The API now ack message sent with a 'done' or 'error' string back. program written for ExaBGP 3.4 will not expect this data and if enough message are sent without being consumed by the api application, the PIPE can become blocking, resulting in ExaBGP stopping to do anything.

# Describe the bug

Please provive a clear and concise description of what the bug is. Again, when running exabgp please use the `-d` options.
It provides a lot of information which can be useful to understand the issue, and please do not obfuscate or on provide a partial output.

Should you prefer to provide the information privately, please let us know where we can reach you.

If you can, please provide us the steps to reproduce the behavior:
- Please include a way to reproduce the issue if possible.
- we use `sudo ./qa/sbin/bgp --port 179 --echo` to similate an IBGP peer

# What we need to help you

Please provide an full output of exabgp running with the "-d" option, including any stacktrace and do NOT edit or obfuscate the output.

# Environment (please complete the following information):

 - OS: [e.g. OSX, Ubuntu, ..]
 - Version [e.g. main, pip version installed, ... ]

# Additional context

Add any other context about the problem here.
