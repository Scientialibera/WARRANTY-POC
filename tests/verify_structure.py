"""
Quick verification test for the new structure
"""
import asyncio
import subprocess
import sys
import time

async def test_structure():
    print("="*80)
    print("STRUCTURE VERIFICATION TEST")
    print("="*80)
    
    # Start servers
    print("\n[1/4] Starting MCP servers...")
    warranty_proc = subprocess.Popen(
        ["python", "-m", "src.servers.warranty.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="C:\\Users\\EmilioArzamendiMcDow\\Documents\\WARRANTY-POC"
    )
    
    actions_proc = subprocess.Popen(
        ["python", "-m", "src.servers.actions.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="C:\\Users\\EmilioArzamendiMcDow\\Documents\\WARRANTY-POC"
    )
    
    time.sleep(3)
    print("✓ Servers started (warranty: port 8002, actions: port 8003)")
    
    # Import agent
    print("\n[2/4] Importing agent module...")
    try:
        from src.agent import create_warranty_agent
        print("✓ Agent module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import agent: {e}")
        warranty_proc.terminate()
        actions_proc.terminate()
        return False
    
    # Create agent
    print("\n[3/4] Creating warranty agent...")
    try:
        agent = create_warranty_agent()
        print("✓ Agent created successfully")
    except Exception as e:
        print(f"✗ Failed to create agent: {e}")
        warranty_proc.terminate()
        actions_proc.terminate()
        return False
    
    # Run simple test
    print("\n[4/4] Running test query...")
    try:
        from agent_framework import ChatMessage
        conversation = [ChatMessage(role='user', text="My product SN-SALT-2024-001234 is not working and I need a replacement!")]
        result = await agent.run(conversation)
        print(f"✓ Agent responded: {result.text[:100]}...")
    except Exception as e:
        print(f"✗ Agent run failed: {e}")
        import traceback
        traceback.print_exc()
        warranty_proc.terminate()
        actions_proc.terminate()
        return False
    
    # Cleanup
    print("\n" + "="*80)
    print("✓ ALL TESTS PASSED - Structure is working correctly!")
    print("="*80)
    
    warranty_proc.terminate()
    actions_proc.terminate()
    
    try:
        warranty_proc.wait(timeout=3)
        actions_proc.wait(timeout=3)
    except:
        warranty_proc.kill()
        actions_proc.kill()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_structure())
    sys.exit(0 if success else 1)
