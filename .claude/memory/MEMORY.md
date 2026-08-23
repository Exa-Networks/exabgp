# ExaBGP Memory

## Release Process
See [release.md](release.md) for full release procedure.

## Posting Anywhere Public
See [posting-attribution.md](posting-attribution.md) - every GitHub post must say Claude wrote it, not Thomas.

## Local Test Environment
- [Functional tests 8KB pipe limit](functional-tests-8kb-pipe-limit.md) — 9 encoding tests fail on Lee's machine only: kernel caps new pipes at 8KB (desktop FIFO pressure), runner's undrained PIPEs deadlock chatty daemons.
