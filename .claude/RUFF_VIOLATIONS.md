# Ruff Violations - ExaBGP Code Quality Analysis

**Date:** 2025-11-09
**Total Violations:** 21,348 (with ALL rules enabled)
**Current Configuration:** Only E9, F63, F7, F82 enabled (critical errors only)

This document catalogs all ruff violations detected when running with `--select ALL`. Items marked with `[*]` are auto-fixable.

---

## 🔴 CRITICAL BUGS - Priority 1 (Must Fix)

### B023 - Lambda Closure Bugs in Loops (63 violations)
**Severity:** CRITICAL
**Auto-fix:** No
**Introduced:** Recent logging lazy evaluation refactor

Loop variables captured in lambdas don't bind correctly - they capture the variable reference, not the value at iteration time.

**Example Locations:**
- `src/exabgp/application/server.py:120` - `lambda: f'{configuration} is not...'`
- `src/exabgp/application/validate.py:50` - `lambda: f'loading {configuration}'`

**Impact:** Logging will show wrong values (last iteration value for all log messages)

**Fix Pattern:**
```python
# WRONG:
for item in items:
    log.info(lambda: f'processing {item}')

# CORRECT:
for item in items:
    log.info(lambda item=item: f'processing {item}')  # Default arg captures value
```

---

### B006 - Mutable Argument Defaults (6 violations)
**Severity:** REVIEW REQUIRED (Not necessarily bugs!)
**Auto-fix:** No - DO NOT USE --unsafe-fixes for this rule!

**⚠️ WARNING:** Many of these are **INTENTIONAL** patterns in this codebase!

Using mutable objects (list, dict) as default arguments can be:
1. **A bug** - unintended shared state across instances
2. **Intentional** - deliberate "static variable" pattern

**Locations:**
- `src/exabgp/conf/yang/code.py:60` - ✅ **INTENTIONAL** `counter={}` - static variable pattern for unique name generation
- `src/exabgp/rib/cache.py:33` - ✅ **INTENTIONAL** `actions=[Action.ANNOUNCE]` - shared default for filtering
- `src/exabgp/bgp/message/open/capability/nexthop.py:26` - ⚠️ **REVIEW** `data=[]` - only read in __init__
- `src/exabgp/bgp/message/update/attribute/aspath.py:81` - ⚠️ **REVIEW** `as_path=[]` - only read in __init__
- `src/exabgp/bgp/message/update/attribute/bgpls/link/sradj.py:36` - ⚠️ **REVIEW** `undecoded=[]`
- `src/exabgp/bgp/message/update/attribute/bgpls/prefix/srprefix.py:38` - ⚠️ **REVIEW** `undecoded=[]`

**Intentional "Static Variable" Pattern:**
```python
# This is INTENTIONAL - counter persists across ALL calls
def _unique(name, counter={}):
    counter[name] = counter.get(name, 0) + 1
    return f'{name}_{counter[name]}'

# To suppress ruff warning:
def _unique(name, counter={}):  # noqa: B006 - intentional static variable
```

**Actual Bug Pattern (if found):**
```python
# BUG - all instances share the same list:
def __init__(self, items=[]):
    self.items = items
    items.append(x)  # Modifies shared default!

# FIX:
def __init__(self, items=None):
    if items is None:
        items = []
    self.items = items
```

**Action:** Manually review each case before "fixing"!

---

### B904 - Missing Exception Chaining (62 violations)
**Severity:** HIGH
**Auto-fix:** No

Raising exceptions in `except` blocks without `from err` loses the original traceback.

**Example Locations:**
- `src/exabgp/bgp/message/refresh.py:71`
- `src/exabgp/bgp/message/update/attribute/aspath.py:206`
- `src/exabgp/configuration/capability.py:54`

**Fix Pattern:**
```python
# WRONG:
except ValueError:
    raise ValueError('invalid value')

# CORRECT:
except ValueError as e:
    raise ValueError('invalid value') from e

# Or explicitly suppress:
except ValueError:
    raise ValueError('invalid value') from None
```

---

### B020 - Loop Variable Overrides Iterator (1 violation)
**Severity:** CRITICAL
**Auto-fix:** No

Loop variable name shadows the iterator, potentially causing infinite loops.

---

### B007 - Unused Loop Control Variable (12 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Loop assigns to variable that's never used. Use `_` for intentionally unused variables.

---

### B008 - Function Call in Default Argument (2 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Calling functions in default arguments evaluated at function definition time, not call time.

---

### B009 - getattr with Constant (3 violations)
**Severity:** LOW
**Auto-fix:** Yes

Using `getattr()` with a constant string - just use attribute access directly.

---

## 🟠 SECURITY ISSUES - Priority 2

### S104 - Hardcoded Bind All Interfaces (8 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Hardcoded `0.0.0.0` could expose service to all network interfaces.

**Locations:**
- `src/exabgp/application/netlink.py:91,95`

---

### S105 - Hardcoded Password String (6 violations)
**Severity:** HIGH
**Auto-fix:** No

Variables named like passwords with hardcoded strings.

---

### S603 - Subprocess Without Shell Equals True (7 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Using subprocess without explicitly setting `shell=False` (default is safe, but explicit is better).

---

### S602 - Subprocess with Shell=True (2 violations)
**Severity:** HIGH
**Auto-fix:** No

Using `shell=True` can enable command injection attacks.

---

### S108 - Hardcoded Temp File (2 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Hardcoded temp file paths can lead to race conditions and security issues.

---

### S311 - Non-Cryptographic Random (2 violations)
**Severity:** LOW
**Auto-fix:** No

Using `random` module instead of `secrets` for security-sensitive operations.

---

### S110 - Try-Except-Pass (4 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Silently swallowing all exceptions with bare `pass` - at minimum log the error.

---

### S101 - Assert Used (1 violation)
**Severity:** LOW
**Auto-fix:** No

Asserts are removed when Python runs with `-O` flag.

---

### S112 - Try-Except-Continue (1 violation)
**Severity:** MEDIUM
**Auto-fix:** No

Exception caught but only continues loop - may hide errors.

---

## 🟡 PYTHON MODERNIZATION (UP prefix) - Priority 3

### UP031 - Printf String Formatting (640 violations) [Auto-fixable]
**Severity:** LOW (Style)
**Auto-fix:** Partial

Old-style `%s` string formatting should use f-strings.

**Example:**
```python
# OLD:
'%s:%s' % (host, port)

# NEW:
f'{host}:{port}'
```

---

### UP004 - Useless Object Inheritance (190 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Python 2 style `class Foo(object):` - just use `class Foo:` in Python 3.

---

### UP024 - OS Error Aliases (48 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Using old OS error names (e.g., `OSError` subclasses) instead of modern equivalents.

---

### UP028 - Yield in For Loop (23 violations)
**Severity:** LOW
**Auto-fix:** No

Can sometimes be simplified to `yield from`.

---

### UP012 - Unnecessary Encode UTF-8 (6 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

`.encode('utf-8')` when UTF-8 is default.

---

### UP037 - Quoted Annotation (5 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Type annotations don't need quotes in Python 3.7+.

---

### UP010 - Unnecessary Future Import (4 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

`from __future__ import` statements that are no longer needed.

---

### UP034 - Extraneous Parentheses (4 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Unnecessary parentheses in expressions.

---

### UP008 - Super Call with Parameters (3 violations)
**Severity:** LOW
**Auto-fix:** No

Python 2 style `super(Class, self)` should be just `super()` in Python 3.

---

### UP036 - Outdated Version Block (3 violations)
**Severity:** LOW
**Auto-fix:** No

Code checking for Python versions that are no longer supported.

---

### UP015 - Redundant Open Modes (2 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Redundant file open modes like `'r'` (the default).

---

### UP018 - Native Literals (2 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Using `str()`, `list()`, etc. instead of literals.

---

## 🟢 CODE QUALITY & COMPLEXITY - Priority 4

### RUF012 - Mutable Class Default (221 violations)
**Severity:** HIGH
**Auto-fix:** No

Class-level mutable defaults (similar to B006 but at class level).

---

### PLR2004 - Magic Value Comparison (176 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Comparing against unnamed numbers/strings. Should use named constants.

**Example:**
```python
# WRONG:
if status == 200:

# BETTER:
HTTP_OK = 200
if status == HTTP_OK:
```

---

### ARG002 - Unused Method Argument (178 violations)
**Severity:** LOW
**Auto-fix:** No

Method parameters that are never used. Prefix with `_` if intentional.

---

### ARG001 - Unused Function Argument (75 violations)
**Severity:** LOW
**Auto-fix:** No

Function parameters that are never used.

---

### ARG003 - Unused Class Method Argument (63 violations)
**Severity:** LOW
**Auto-fix:** No

Class method parameters that are never used.

---

### ARG005 - Unused Lambda Argument (34 violations)
**Severity:** LOW
**Auto-fix:** No

Lambda parameters that are never used.

---

### ARG004 - Unused Static Method Argument (24 violations)
**Severity:** LOW
**Auto-fix:** No

Static method parameters that are never used.

---

### C901 - Complex Structure (60 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Functions with high cyclomatic complexity (>10). Consider refactoring.

---

### PLR0913 - Too Many Arguments (45 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Functions with more than 5 parameters. Consider using a config object.

---

### PLR0912 - Too Many Branches (40 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Functions with more than 12 branches. Consider refactoring.

---

### PLR0915 - Too Many Statements (20 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Functions with more than 50 statements. Consider breaking up.

---

### PLR0911 - Too Many Return Statements (9 violations)
**Severity:** LOW
**Auto-fix:** No

Functions with more than 6 return statements.

---

### PLR1714 - Repeated Equality Comparison (16 violations)
**Severity:** LOW
**Auto-fix:** No

Multiple equality checks that could use `in`.

**Example:**
```python
# WRONG:
if x == 1 or x == 2 or x == 3:

# BETTER:
if x in (1, 2, 3):
```

---

### PLR1704 - Redefined Argument from Local (8 violations)
**Severity:** LOW
**Auto-fix:** No

Function argument name reused as local variable.

---

### PLW2901 - Redefined Loop Name (12 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Loop variable reassigned inside loop body.

---

### PLW0603 - Global Statement (3 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Using global variables - consider refactoring.

---

### PLW1509 - Subprocess Popen Preexec Fn (3 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Using `preexec_fn` in subprocess which is not thread-safe.

---

### PLW0127 - Self Assigning Variable (2 violations)
**Severity:** HIGH
**Auto-fix:** No

Variable assigned to itself - likely a bug.

---

### PLW0128 - Redeclared Assigned Name (2 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Variable redeclared in same scope.

---

### PLW1508 - Invalid Envvar Default (1 violation)
**Severity:** MEDIUM
**Auto-fix:** No

Invalid default value for environment variable.

---

### PLC0206 - Dict Index Missing Items (4 violations)
**Severity:** LOW
**Auto-fix:** No

Dictionary unpacking could use `.items()`.

---

### PLC1802 - Len Test (2 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Using `len(x) == 0` instead of `not x`.

---

### PLE0302 - Unexpected Special Method Signature (1 violation)
**Severity:** HIGH
**Auto-fix:** No

Special method with wrong signature.

---

### PLR0402 - Manual From Import (1 violation) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Import pattern that could be simplified.

---

### BLE001 - Blind Except (24 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Catching bare `Exception` or too broad exception types.

---

## 🔵 PERFORMANCE (PERF prefix) - Priority 5

### PERF203 - Try-Except in Loop (8 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Try-except block inside loop - move outside if possible for better performance.

---

### PERF401 - Manual List Comprehension (7 violations)
**Severity:** LOW
**Auto-fix:** No

Manually building lists that could use list comprehension.

---

## ⚪ STYLE & READABILITY - Priority 6

### Q000 - Bad Quotes Inline String (13,016 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

**Status:** Already discussed - keeping single quotes as project style.

---

### I001 - Unsorted Imports (256 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Imports not sorted alphabetically or by type (stdlib, third-party, local).

---

### COM812 - Missing Trailing Comma (140 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Multi-line collections missing trailing comma on last element.

---

### E501 - Line Too Long (114 violations)
**Severity:** LOW
**Auto-fix:** No

Lines exceeding 120 characters (project's configured limit).

---

### ERA001 - Commented Out Code (200 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Code commented out instead of removed. Use version control instead.

---

### SIM102 - Collapsible If (22 violations)
**Severity:** LOW
**Auto-fix:** No

Nested if statements that could be combined with `and`.

---

### SIM118 - In Dict Keys (22 violations)
**Severity:** LOW
**Auto-fix:** No

Using `key in dict.keys()` instead of `key in dict`.

---

### SIM108 - If-Else Block Instead of If-Exp (13 violations)
**Severity:** LOW
**Auto-fix:** No

If-else that could be ternary operator.

---

### SIM103 - Needless Bool (10 violations)
**Severity:** LOW
**Auto-fix:** No

Unnecessary boolean conversion.

---

### SIM105 - Suppressible Exception (11 violations)
**Severity:** LOW
**Auto-fix:** No

Try-except-pass that could use `contextlib.suppress()`.

---

### SIM110 - Reimplemented Builtin (3 violations)
**Severity:** LOW
**Auto-fix:** No

Manually implementing functionality available in builtins.

---

### SIM112 - Uncapitalized Environment Variables (19 violations)
**Severity:** LOW
**Auto-fix:** No

Environment variable names not in UPPER_CASE.

---

### SIM114 - If With Same Arms (5 violations) [Auto-fixable]
**Severity:** MEDIUM
**Auto-fix:** Yes

If-else branches with identical code.

---

### SIM115 - Open File With Context Handler (4 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Opening files without context manager (`with` statement).

---

### SIM300 - Yoda Conditions (9 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Reversed comparisons like `if 5 == x:` instead of `if x == 5:`.

---

### C408 - Unnecessary Collection Call (34 violations)
**Severity:** LOW
**Auto-fix:** No

Using `dict()`, `list()`, etc. instead of literal syntax.

---

### C402 - Unnecessary Generator Dict (12 violations)
**Severity:** LOW
**Auto-fix:** No

Generator expression passed to `dict()` that could be dict comprehension.

---

### C403 - Unnecessary List Comprehension Set (2 violations)
**Severity:** LOW
**Auto-fix:** No

List comprehension passed to `set()` that could be set comprehension.

---

### C404 - Unnecessary List Comprehension Dict (10 violations)
**Severity:** LOW
**Auto-fix:** No

List comprehension passed to `dict()` that could be dict comprehension.

---

### C405 - Unnecessary Literal Set (8 violations)
**Severity:** LOW
**Auto-fix:** No

Using `set([])` instead of set literal `{}`.

---

### C413 - Unnecessary Call Around Sorted (1 violation)
**Severity:** LOW
**Auto-fix:** No

Unnecessary list() or reversed() call around sorted().

---

### C416 - Unnecessary Comprehension (5 violations)
**Severity:** LOW
**Auto-fix:** No

Comprehension that could be simplified.

---

### C417 - Unnecessary Map (1 violation)
**Severity:** LOW
**Auto-fix:** No

Using map() where list comprehension would be clearer.

---

### ISC001 - Single Line Implicit String Concatenation (2 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Implicit string concatenation on single line.

---

## 📝 DOCUMENTATION (D prefix) - Priority 7

### D102 - Undocumented Public Method (1,019 violations)
**Severity:** LOW
**Auto-fix:** No

Public methods missing docstrings.

---

### D105 - Undocumented Magic Method (520 violations)
**Severity:** LOW
**Auto-fix:** No

Magic methods (`__init__`, `__str__`, etc.) missing docstrings.

---

### D101 - Undocumented Public Class (405 violations)
**Severity:** LOW
**Auto-fix:** No

Public classes missing docstrings.

---

### D103 - Undocumented Public Function (354 violations)
**Severity:** LOW
**Auto-fix:** No

Public functions missing docstrings.

---

### D107 - Undocumented Public Init (233 violations)
**Severity:** LOW
**Auto-fix:** No

`__init__` methods missing docstrings.

---

### D106 - Undocumented Public Nested Class (107 violations)
**Severity:** LOW
**Auto-fix:** No

Nested classes missing docstrings.

---

### D100 - Undocumented Public Module (29 violations)
**Severity:** LOW
**Auto-fix:** No

Module-level docstrings missing.

---

### D104 - Undocumented Public Package (17 violations)
**Severity:** LOW
**Auto-fix:** No

`__init__.py` files missing docstrings.

---

### D212 - Multi-Line Summary First Line (293 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Docstring multi-line summary formatting.

---

### D400 - Missing Trailing Period (317 violations)
**Severity:** LOW
**Auto-fix:** No

Docstring first line doesn't end with period.

---

### D415 - Missing Terminal Punctuation (317 violations)
**Severity:** LOW
**Auto-fix:** No

Docstring first line doesn't end with proper punctuation.

---

### D401 - Non-Imperative Mood (3 violations)
**Severity:** LOW
**Auto-fix:** No

Docstrings should use imperative mood ("Return" not "Returns").

---

### D403 - First Word Uncapitalized (5 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Docstring first word should be capitalized.

---

### D205 - Missing Blank Line After Summary (6 violations)
**Severity:** LOW
**Auto-fix:** No

Multi-line docstrings need blank line after summary.

---

## 🔧 TYPE ANNOTATIONS (ANN prefix) - Priority 8

### ANN001 - Missing Type Function Argument (3,023 violations)
**Severity:** LOW
**Auto-fix:** No

Function arguments missing type hints.

---

### ANN201 - Missing Return Type Undocumented Public Function (1,082 violations)
**Severity:** LOW
**Auto-fix:** No

Public functions missing return type annotations.

---

### ANN204 - Missing Return Type Special Method (784 violations)
**Severity:** LOW
**Auto-fix:** No

Special methods missing return type annotations.

---

### ANN202 - Missing Return Type Private Function (331 violations)
**Severity:** LOW
**Auto-fix:** No

Private functions missing return type annotations.

---

### ANN206 - Missing Return Type Class Method (247 violations)
**Severity:** LOW
**Auto-fix:** No

Class methods missing return type annotations.

---

### ANN205 - Missing Return Type Static Method (92 violations)
**Severity:** LOW
**Auto-fix:** No

Static methods missing return type annotations.

---

### ANN002 - Missing Type Args (11 violations)
**Severity:** LOW
**Auto-fix:** No

`*args` missing type hint.

---

### ANN003 - Missing Type Kwargs (7 violations)
**Severity:** LOW
**Auto-fix:** No

`**kwargs` missing type hint.

---

## 📋 EXCEPTIONS & ERROR HANDLING (TRY prefix)

### TRY003 - Raise Vanilla Args (313 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Raising exceptions with string messages instead of custom exception classes.

---

### TRY002 - Raise Vanilla Class (48 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Raising built-in exceptions instead of custom ones.

---

### TRY300 - Try Consider Else (18 violations)
**Severity:** LOW
**Auto-fix:** No

Try-except could use else clause for clearer logic.

---

### TRY301 - Raise Within Try (8 violations)
**Severity:** LOW
**Auto-fix:** No

Raising exceptions within try block (could move to else).

---

### TRY004 - Type Check Without Type Error (3 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Type checking without catching TypeError.

---

### TRY201 - Verbose Raise (5 violations)
**Severity:** LOW
**Auto-fix:** No

Using `raise exc` instead of just `raise` in except block.

---

## 📂 PATH OPERATIONS (PTH prefix)

### PTH118 - os.path.join (24 violations)
**Severity:** LOW
**Auto-fix:** No

Using `os.path.join()` instead of pathlib.

---

### PTH100 - os.path.abspath (17 violations)
**Severity:** LOW
**Auto-fix:** No

Using `os.path.abspath()` instead of pathlib.

---

### PTH123 - builtin open (11 violations)
**Severity:** LOW
**Auto-fix:** No

Using builtin `open()` instead of pathlib `.open()`.

---

### PTH110 - os.path.exists (9 violations)
**Severity:** LOW
**Auto-fix:** No

Using `os.path.exists()` instead of pathlib.

---

### PTH113 - os.path.isfile (6 violations)
**Severity:** LOW
**Auto-fix:** No

Using `os.path.isfile()` instead of pathlib.

---

### PTH109 - os.getcwd (5 violations)
**Severity:** LOW
**Auto-fix:** No

Using `os.getcwd()` instead of pathlib.

---

### PTH116 - os.stat (3 violations)
**Severity:** LOW
**Auto-fix:** No

Using `os.stat()` instead of pathlib.

---

### PTH120 - os.path.dirname (3 violations)
**Severity:** LOW
**Auto-fix:** No

Using `os.path.dirname()` instead of pathlib.

---

### PTH204 - os.path.getmtime (3 violations)
**Severity:** LOW
**Auto-fix:** No

Using `os.path.getmtime()` instead of pathlib.

---

## 🔍 RETURN STATEMENTS (RET prefix)

### RET505 - Superfluous Else Return (29 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Unnecessary else after return statement.

---

### RET503 - Implicit Return (17 violations)
**Severity:** LOW
**Auto-fix:** No

Function has implicit return None.

---

### RET504 - Unnecessary Assign (17 violations)
**Severity:** LOW
**Auto-fix:** No

Assigning to variable only to immediately return it.

---

### RET502 - Implicit Return Value (4 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Returning None implicitly instead of explicitly.

---

## 🐛 PIE (misc improvements)

### PIE790 - Unnecessary Placeholder (7 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Unnecessary `pass` or `...` statements.

---

### PIE804 - Unnecessary Dict Kwargs (6 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Using `dict(**kwargs)` unnecessarily.

---

### PIE808 - Unnecessary Range Start (4 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Using `range(0, n)` instead of `range(n)`.

---

### PIE800 - Unnecessary Spread (3 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Unnecessary unpacking operator.

---

### PIE794 - Duplicate Class Field Definition (2 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Class field defined multiple times.

---

### PIE810 - Multiple Starts Ends With (2+ violations)
**Severity:** LOW
**Auto-fix:** No

Multiple `.startswith()` or `.endswith()` calls that could be combined.

---

## 🔢 NAMING CONVENTIONS (N prefix)

### N806 - Non-Lowercase Variable in Function (20 violations)
**Severity:** LOW
**Auto-fix:** No

Variables in functions should be lowercase.

---

### N801 - Invalid Class Name (8 violations)
**Severity:** LOW
**Auto-fix:** No

Class names should be CamelCase.

---

### N802 - Invalid Function Name (8 violations)
**Severity:** LOW
**Auto-fix:** No

Function names should be lowercase_with_underscores.

---

### N818 - Error Suffix on Exception Name (8 violations)
**Severity:** LOW
**Auto-fix:** No

Exception class names should end with "Error".

---

### N805 - Invalid First Argument Name for Method (4 violations)
**Severity:** LOW
**Auto-fix:** No

First argument of method should be `self`.

---

### N804 - Invalid First Argument Name for Class Method (3 violations)
**Severity:** LOW
**Auto-fix:** No

First argument of classmethod should be `cls`.

---

## 📝 TODO COMMENTS (TD/FIX prefix)

### TD002 - Missing TODO Author (121 violations)
**Severity:** LOW
**Auto-fix:** No

TODO comments should include author.

---

### TD003 - Missing TODO Link (120 violations)
**Severity:** LOW
**Auto-fix:** No

TODO comments should link to issue tracker.

---

### TD001 - Invalid TODO Tag (108 violations)
**Severity:** LOW
**Auto-fix:** No

Using informal TODO format.

---

### FIX003 - Line Contains XXX (104 violations)
**Severity:** LOW
**Auto-fix:** No

XXX comments found (lower priority than FIXME).

---

### FIX002 - Line Contains TODO (13 violations)
**Severity:** LOW
**Auto-fix:** No

TODO comments found.

---

### FIX001 - Line Contains FIXME (4 violations)
**Severity:** MEDIUM
**Auto-fix:** No

FIXME comments found (should be addressed).

---

### TD005 - Missing TODO Description (3 violations)
**Severity:** LOW
**Auto-fix:** No

TODO comment missing description.

---

## 🖨️ DEBUG & LOGGING

### T201 - Print (76 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Using `print()` instead of proper logging.

---

### T100 - Debugger (10 violations)
**Severity:** HIGH
**Auto-fix:** No

Debugger statements (`breakpoint()`, `pdb.set_trace()`) left in code.

---

### T203 - pprint (9 violations)
**Severity:** LOW
**Auto-fix:** No

Using `pprint()` instead of logging.

---

### G004 - Logging F-String (8 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Using f-strings in logging (prevents lazy evaluation).

**Example:**
```python
# WRONG:
log.info(f'Processing {item}')

# CORRECT:
log.info('Processing %s', item)
# OR with lazy evaluation:
log.info(lambda: f'Processing {item}')
```

---

### G010 - Logging Warn (3 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Using deprecated `log.warn()` instead of `log.warning()`.

---

## 🔄 ERROR MESSAGES (EM prefix)

### EM101 - Raw String in Exception (229 violations)
**Severity:** LOW
**Auto-fix:** No

Exception messages should be defined as constants for i18n.

---

### EM102 - F-String in Exception (87 violations)
**Severity:** LOW
**Auto-fix:** No

Exception messages with f-strings should use variables.

---

## 📦 MISC RUFF-SPECIFIC (RUF prefix)

### RUF012 - Mutable Class Default (221 violations)
**Severity:** HIGH
**Auto-fix:** No

Class attributes with mutable defaults (see B006).

---

### RUF100 - Unused NOQA (24 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

`# noqa` comments that are no longer needed.

---

### RUF010 - Explicit F-String Type Conversion (41 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Using `f'{str(x)}'` instead of `f'{x!s}'`.

---

### RUF005 - Collection Literal Concatenation (17 violations)
**Severity:** LOW
**Auto-fix:** No

Concatenating collection literals instead of using single literal.

---

## 🏗️ SHADOWING (A prefix)

### A001 - Builtin Variable Shadowing (7 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Variable name shadows Python builtin (e.g., `id`, `type`, `list`).

---

### A002 - Builtin Argument Shadowing (3 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Function argument shadows Python builtin.

---

## 🔧 MISC CODE QUALITY

### PYI024 - Collections Named Tuple (12 violations)
**Severity:** LOW
**Auto-fix:** No

Using `collections.namedtuple` instead of `typing.NamedTuple`.

---

### PGH004 - Blanket NOQA (12 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Using bare `# noqa` instead of specific codes.

---

### RSE102 - Unnecessary Paren on Raise Exception (7 violations) [Auto-fixable]
**Severity:** LOW
**Auto-fix:** Yes

Unnecessary parentheses when raising exception.

---

### INP001 - Implicit Namespace Package (6 violations)
**Severity:** LOW
**Auto-fix:** No

Missing `__init__.py` in package directory.

---

### FA100 - Future Rewritable Type Annotation (3 violations)
**Severity:** LOW
**Auto-fix:** No

Type annotation that will break in future Python versions.

---

### EXE001 - Shebang Not Executable (3 violations)
**Severity:** LOW
**Auto-fix:** No

File has shebang but is not executable.

---

### EXE002 - Shebang Missing Executable File (2 violations)
**Severity:** LOW
**Auto-fix:** No

Executable file missing shebang.

---

### SLF001 - Private Member Access (22 violations)
**Severity:** LOW
**Auto-fix:** No

Accessing private members (starting with `_`) from outside class.

---

### FBT003 - Boolean Positional Value in Call (60 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Passing boolean literals as positional arguments (hard to read).

---

### FBT002 - Boolean Default Value Positional Argument (35 violations)
**Severity:** MEDIUM
**Auto-fix:** No

Boolean default values for positional arguments (should be keyword-only).

---

---

## 🎯 RECOMMENDED FIX ORDER

### Phase 1: Critical Bugs (Must Fix)
1. **B023** (63) - Lambda closure bugs - **BREAKS LOGGING**
2. **T100** (10) - Remove debugger statements
3. **PLW0127** (2) - Self-assigning variables (likely bugs)
4. ~~**B006** (6) - Mutable defaults~~ - **SKIP: Mostly intentional patterns in this codebase**

### Phase 2: Security & Stability
5. **S105** (6) - Hardcoded passwords
6. **S602** (2) - Shell injection risks
7. **B904** (62) - Exception chaining (better debugging)
8. **BLE001** (24) - Blind excepts

### Phase 3: Code Quality (High Impact)
9. **RUF012** (221) - Mutable class defaults
10. **ERA001** (200) - Commented-out code
11. **T201** (76) - Print statements → logging
12. **G004** (8) - F-strings in logging

### Phase 4: Auto-fixable Modernization
13. **UP031** (640) - Printf formatting (if desired)
14. **UP004** (190) - Object inheritance
15. **I001** (256) - Import sorting
16. **COM812** (140) - Trailing commas
17. **UP024** (48) - OS error aliases

### Phase 5: Style & Consistency
18. **SIM*** - Simplification rules (various)
19. **C4*** - Comprehension improvements
20. **RET*** - Return statement improvements

### Phase 6: Documentation (Low Priority)
21. **D*** - Docstrings (1,000+)
22. **ANN*** - Type hints (5,000+)

### Phase 7: Optional/Nice-to-Have
23. **TD/FIX*** - TODO/FIXME cleanup
24. **PTH*** - Pathlib migration
25. **N*** - Naming conventions

---

## 📊 STATISTICS SUMMARY

| Category | Count | Auto-Fix | Priority |
|----------|-------|----------|----------|
| Critical Bugs | 143 | Partial | P1 |
| Security | 32 | No | P2 |
| Modernization | 920+ | Yes | P3 |
| Code Quality | 1,200+ | Partial | P4 |
| Performance | 15 | No | P5 |
| Style | 13,900+ | Yes | P6 |
| Documentation | 2,400+ | No | P7 |
| Type Hints | 5,200+ | No | P8 |
| **TOTAL** | **21,348** | ~40% | - |

---

## 🛠️ CONFIGURATION NOTES

Current `pyproject.toml` configuration only enables critical errors:
```toml
[tool.ruff.lint]
select = ["E9", "F63", "F7", "F82"]
```

To enable specific categories, update to:
```toml
[tool.ruff.lint]
select = [
    "E9",   # Runtime/syntax errors
    "F63",  # Invalid print statements
    "F7",   # Syntax errors in docstrings
    "F82",  # Undefined names in __all__
    "B",    # Bugbear (common bugs)
    "S",    # Security
    # Add more as needed
]
```

---

**Last Updated:** 2025-11-09
**Generated by:** Claude Code
