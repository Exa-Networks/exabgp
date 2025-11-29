convert FSM to use IntEnum 
convert code to use async

  📋 Complete Report: | None Annotations in Application Module

  32 Total | None Annotations

  ---
  🟢 EASY FIXES (Can Remove Now)

  | File      | Line | Current              | Fix    | Reason                                |
  |-----------|------|----------------------|--------|---------------------------------------|
  | decode.py | 55   | main() -> int | None | -> int | cmdline() always returns int (0 or 1) |
  | encode.py | 67   | main() -> int | None | -> int | cmdline() always returns int (0)      |

  ---
  🟡 MEDIUM FIXES (Bug Fix + Type Improvement)

  | File    | Line  | Issue                                                                                    | Fix                                 |
  |---------|-------|------------------------------------------------------------------------------------------|-------------------------------------|
  | pipe.py | 66-88 | check_fifo() -> bool | None has 3 duplicate except OSError blocks - only first reachable | Remove dead code, change to -> bool |

  ---
  🔴 UPSTREAM TYPE ISSUES (Environment/HashTable)

  | File      | Line          | Code                                     | Root Cause                        |
  |-----------|---------------|------------------------------------------|-----------------------------------|
  | server.py | 182, 221, 231 | if env.api.pipename is None              | HashTable.__getattr__ returns Any |
  | run.py    | 263-264       | pipename, socketname from getenv().api.* | Same - type info lost             |

  Upstream Fix Options:
  1. Add typed properties to Env class for known fields
  2. Use TypedDict for HashTable sections
  3. Create typed wrapper class for api section

  ---
  ⚪ LEGITIMATELY OPTIONAL (Cannot Remove)

  Signal Handlers (Python requires FrameType | None)

  | File          | Line | Annotation              |
  |---------------|------|-------------------------|
  | flow.py       | 117  | frame: FrameType | None |
  | unixsocket.py | 196  | signum: int | None      |

  Optional Function Parameters (User Choice)

  | File           | Line          | Annotation                | Reason                        |
  |----------------|---------------|---------------------------|-------------------------------|
  | cli.py         | 33-34         | history_file, daemon_uuid | Optional CLI features         |
  | healthcheck.py | 191           | name: str | None          | Optional healthcheck name     |
  | healthcheck.py | 227, 301, 330 | label: str | None         | Optional IP label filter      |
  | healthcheck.py | 359           | user, group               | Optional privilege drop       |
  | healthcheck.py | 381           | cmd: str | None           | Optional health check command |
  | healthcheck.py | 226           | ip_ifnames: dict | None   | Optional interface mapping    |
  | server.py      | 48            | delay: int | None         | Optional delayed signal       |
  | run.py         | 328, 392, 421 | pipename, socketname      | Optional transport names      |
  | tojson.py      | 113           | result: str | None        | Transcoder may return None    |

  Argparse with default=None (Semantic - "Not Provided")

  | File           | Lines             | Arguments                                    |
  |----------------|-------------------|----------------------------------------------|
  | healthcheck.py | 114, 121-128, 130 | --label, --community, --*-as-path, --path-id |
  | decode.py      | 48-49             | --configuration, --family                    |
  | encode.py      | 61                | --configuration                              |
  | run.py         | 114, 118          | --pipename, --batch                          |
  | server.py      | 70                | --signal                                     |

  Note: These use None to mean "not provided" and check if value: or if value is not None:. Changing to default='' would require updating all usage sites.

  ---
  Instance State Variables (Start as None, Set Later)

  | File          | Line    | Variable                                | Pattern          |
  |---------------|---------|-----------------------------------------|------------------|
  | pipe.py       | 97      | self.r_pipe: int | None                 | Set in loop()    |
  | unixsocket.py | 101-103 | server_socket, client_socket, client_fd | Socket lifecycle |

  Fix Option: Initialize in __init__ with sentinel or restructure to avoid None state.

  ---
  Collections with Optional Elements

  | File          | Line          | Type                                    | Reason                     |
  |---------------|---------------|-----------------------------------------|----------------------------|
  | pipe.py       | 133, 248      | list[int | None], dict[int | None, ...] | self.r_pipe can be None    |
  | unixsocket.py | 204, 295, 299 | Same pattern                            | self.client_fd can be None |

  ---
  Complex Return Type (Dual Behavior)

  | File    | Line    | Function                            | Issue                                          |
  |---------|---------|-------------------------------------|------------------------------------------------|
  | run.py  | 124     | send_command_socket() -> str | None | Returns str when return_output=True, else None |
  | main.py | 27, 133 | main() -> int | None                | argparse.func is Callable[..., Any]            |

  Fix Option: Use @overload or split into two functions.

  ---
  📊 Summary

  | Category              | Count   | Fixable?                               |
  |-----------------------|---------|----------------------------------------|
  | Easy fixes            | 2       | ✅ Now                                  |
  | Bug fix (dead code)   | 1       | ✅ Now                                  |
  | Upstream (HashTable)  | ~5 uses | 🔧 Requires environment module changes |
  | Legitimately optional | ~20     | ❌ By design                            |
  | Complex/restructure   | ~4      | 🔧 Would need API changes              |

  Recommended Actions:
  1. ✅ Fix decode.py and encode.py main() return types
  2. ✅ Fix pipe.py dead code bug
  3. 🔧 Consider typed Env properties for api.pipename/api.socketname
