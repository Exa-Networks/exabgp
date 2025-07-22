# In your relevant Flow/EdgeFlow definition file
from exabgp.bgp.message.update.nlri.flow import Flow, EdgeFlow, Flow4Source
import socket

def analyze_flow_behavior():
    """
    This function will help us understand exactly how Flow works
    and what the test expects.
    """

    # Step 1: Create a basic Flow instance
    # (You'll need to adjust these parameters based on actual Flow constructor)
    test_flow = Flow()
    test_flow.add(Flow4Source(socket.inet_pton(socket.AF_INET, '192.168.1.0'), 24))

    print("=== FLOW CLASS ANALYSIS ===")
    print(f"Flow instance created: {test_flow}")
    print(f"Type: {type(test_flow)}")

    # Step 2: Examine all methods available
    print("\nAvailable methods:")
    for method in dir(test_flow):
        if not method.startswith('_'):
            print(f"  - {method}")

    # Step 3: Test extensive() output
    print("\n=== EXTENSIVE OUTPUT ===")
    extensive_output = test_flow.extensive()
    print(repr(extensive_output))  # Using repr to see exact string format
    print("\nFormatted output:")
    print(extensive_output)

    # Step 4: Test __str__ output
    print("\n=== STR OUTPUT ===")
    str_output = str(test_flow)
    print(repr(str_output))

    # Step 5: Now test EdgeFlow
    print("\n=== EDGE FLOW ANALYSIS ===")
    edge_flow = EdgeFlow(
        device_id='edge-router-01',
    )
    edge_flow.add(Flow4Source(socket.inet_pton(socket.AF_INET, '192.168.1.0'), 24))


    print(f"EdgeFlow instance: {edge_flow}")
    print(f"Device ID accessible: {hasattr(edge_flow, 'device_id')}")
    if hasattr(edge_flow, 'device_id'):
        print(f"Device ID value: {edge_flow.device_id}")

    # Step 6: Compare outputs
    print("\n=== EDGE FLOW EXTENSIVE ===")
    try:
        edge_extensive = edge_flow.extensive()
        print(repr(edge_extensive))
        print("\nFormatted:")
        print(edge_extensive)
    except Exception as e:
        print(f"Error calling extensive(): {type(e).__name__}: {e}")

    # Step 7: Analyze the test expectation
    print("\n=== TEST EXPECTATION ANALYSIS ===")
    print("The test expects 'device-id' to appear in the output.")
    print("Looking for the exact format required...")

    # Check if device-id appears in the output
    if hasattr(edge_flow, 'extensive'):
        try:
            output = edge_flow.extensive()
            if 'device-id' in output:
                print("✓ 'device-id' found in output")
            else:
                print("✗ 'device-id' NOT found in output")
                print("This is why the test is failing.")
        except:
            print("✗ Cannot call extensive() method")

# Run the analysis
if __name__ == "__main__":
    analyze_flow_behavior()
