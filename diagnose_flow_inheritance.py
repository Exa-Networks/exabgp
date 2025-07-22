from exabgp.bgp.message.update.nlri.flow import Flow, EdgeFlow
import inspect

def trace_inheritance():
    """
    Let's understand the complete picture of how these classes relate
    """

    print("=== INHERITANCE CHAIN ===")

    # Trace Flow's inheritance
    print(f"Flow inherits from: {Flow.__bases__}")

    # Check if NLRI is in the chain
    for base in Flow.__bases__:
        print(f"  {base.__name__} inherits from: {base.__bases__}")

        # Check methods at each level
        print(f"  {base.__name__} defines these methods:")
        for name, method in inspect.getmembers(base, predicate=inspect.isfunction):
            if name in ['__str__', 'extensive', '__repr__']:
                print(f"    - {name}")

    # Now check what EdgeFlow actually has
    print("\n=== EDGEFLOW METHOD RESOLUTION ORDER ===")
    for cls in EdgeFlow.__mro__:
        print(f"  {cls.__name__}")
        if hasattr(cls, 'extensive'):
            print(f"    ✓ Has extensive method")
        if hasattr(cls, '__str__'):
            print(f"    ✓ Has __str__ method")

trace_inheritance()
