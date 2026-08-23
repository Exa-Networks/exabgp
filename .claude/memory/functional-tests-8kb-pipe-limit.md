---
name: functional-tests-8kb-pipe-limit
description: 9 functional encoding tests fail locally (not CI) because this machine caps new pipes at 8KB, deadlocking the undrained runner pipes
metadata:
  type: project
---

On Lee's workstation (CachyOS, 2026-08-22), `./qa/bin/functional encoding` fails 9 tests
[6, 7, 8, M, U, V, X, a, b] that pass in CI and pass locally in split `--server`/`--client` mode.

**Root cause (verified, not a code regression):**
- Desktop apps (Steam, Firefox — ~2800 open FIFOs) push the user past
  `fs.pipe-user-pages-soft` (16384 pages), so the kernel caps every **new pipe at 8192 bytes**
  instead of 64KB. Verify with: `python3 -c "import os,fcntl; r,w=os.pipe(); print(fcntl.fcntl(r,1032))"`.
- The runner (`qa/bin/functional`, `Exec.run` ~line 544) spawns server/client with
  `stdout=PIPE, stderr=PIPE` and only drains them via `communicate()` **after** exit.
- Any test daemon logging >8KB blocks in `write()` (`/proc/PID/wchan` = `anon_pipe_write`),
  freezing the whole asyncio loop — socket goes unread (CLOSE-WAIT with queued keepalives),
  updates stop, test times out. SIGKILL then loses buffered log tail, making the daemon
  appear to "stop at update 12".
- The 9 failing tests are exactly the chattiest ones (>8KB daemon output); test 2 emits ~10KB
  total across 4 streams and passes.

**Why:** Distinguish this environmental failure from real regressions before debugging
encoding tests on this machine.

**How to apply:** If these 9 tests fail together locally, first check pipe capacity with the
one-liner above. Workarounds: close desktop apps / raise `fs.pipe-user-pages-soft`, or run
tests split-mode. Real fix (needs explicit request): drain pipes concurrently in
`qa/bin/functional` (reader threads or tempfile-backed stdout/stderr). Latent even at 64KB
for any future chattier test. Related daemon-side weakness: synchronous log writes can block
the entire reactor event loop.
