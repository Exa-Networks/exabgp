# API Functional Tests

Tests for the ExaBGP v6 API that validate JSON responses from all API commands.

## Overview

Unlike encoding tests (which validate BGP wire format), API tests validate:
- JSON response structure
- Command execution success/failure
- Error handling

## Test Files

| File | Description |
|------|-------------|
| `api-v6-comprehensive.ci` | Tests all 43+ v6 API commands |

## Running Tests

```bash
# Run all API tests
./qa/bin/functional api

# Run specific test
./qa/bin/functional api A

# List available tests
./qa/bin/functional api --list

# Verbose output
./qa/bin/functional api -v
```

## Test File Format

### `.ci` file
Single line with config filename(s) from `etc/exabgp/`:
```
api-v6-comprehensive.conf
```

### Configuration file
ExaBGP config with process definition pointing to test script:
```
process api-test {
    run ./run/api-v6-comprehensive.run;
    encoder json;
}

neighbor 127.0.0.1 {
    ...
    api { processes [ api-test ]; }
}
```

### Test script (`.run` file)
Python script in `etc/exabgp/run/` that:
1. Sends v6 API commands via stdout
2. Reads JSON responses from stdin
3. Validates responses against expected patterns
4. Exits 0 on success, non-zero on failure
5. Prints "SUCCESS" on pass or "FAILURE" on fail

## Success Criteria

API test passes when:
- Test script exit code is 0
- Output contains "SUCCESS"

## Adding New API Tests

1. Create `.ci` file in `qa/api/`
2. Create config file in `etc/exabgp/`
3. Create test script in `etc/exabgp/run/`
4. Register test in `qa/bin/functional` (APITests class)

## Related Documentation

- `.claude/exabgp/FUNCTIONAL_TEST_RUNNER.md` - Test runner architecture
- `plan/api-v6-test.md` - Implementation plan
