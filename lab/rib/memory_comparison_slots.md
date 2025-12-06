# Memory Comparison: Before and After __slots__

## Test Configuration
- 100,000 IPv4 unicast routes
- Route objects with INET NLRI and AttributeCollection

## Results

| Metric | Before __slots__ | After __slots__ | Savings |
|--------|------------------|-----------------|---------|
| Route objects (100K) | 98.61 MB | 66.57 MB | **32.04 MB (32%)** |
| Bytes per route | 1,034 bytes | 698 bytes | **336 bytes (32%)** |
| Total for 100K | 112.34 MB | 80.29 MB | **32.05 MB (29%)** |

## Class Configuration

### Before
- Route: `__slots__=False`, `__dict__=True` (296 bytes)
- INET: `__slots__=False`, `__dict__=True` (296 bytes)

### After
- Route: `__slots__=True`, `__dict__=False`
- INET: `__slots__=True`, `__dict__=False`

## Analysis

The `__slots__` optimization achieved:
- **32% reduction** in Route object memory
- **336 bytes saved** per route
- **32 MB saved** for 100K routes

The savings are larger than the initial estimate of ~104 bytes because:
1. Both Route AND NLRI classes now use `__slots__`
2. Eliminates `__dict__` overhead on both classes (~192 bytes each)
3. PathInfo also uses `__slots__`

## Files Modified
- `src/exabgp/rib/route.py` - Route class
- `src/exabgp/protocol/family.py` - Family base class
- `src/exabgp/bgp/message/update/nlri/*.py` - All NLRI classes
- `src/exabgp/bgp/message/update/nlri/qualifier/path.py` - PathInfo

## Commit
`3808601e feat: Add __slots__ to NLRI and Route classes for memory optimization`
