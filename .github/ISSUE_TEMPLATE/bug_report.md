---
name: Bug report
about: Create a report to help us improve
title: ''
labels: bug
assignees: thomas-mangin

---

** Bug Report **

We are sorry that you are experiencing an issue with ExaBGP.

Before opening this issue could you please:
 - make sure the problem was not already reported to avoid duplicates.
 - check if the problem is still present on the latest version (main)
 - provide an full output of exabgp running with the "-d" option, including any stacktrace
   (please provide the full output - even if long)

**Describe the bug**

A clear and concise description of what the bug is.

**To Reproduce**

Steps to reproduce the behavior:
- Please include a way to reproduce the issue if possible.
- we use `sudo ./qa/sbin/bgp --port 179 --echo` to similate an IBGP peer

**Expected behavior**

A clear and concise description of what you expected to happen.

**Environment (please complete the following information):**

 - OS: [e.g. OSX, Ubuntu, ..]
 - Version [e.g. main, pip version installed, ... ]

**Additional context**

Add any other context about the problem here.
