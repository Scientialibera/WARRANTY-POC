"""
Interactive Warranty Agent Test

Run the agent in interactive mode where you can type messages and see responses.
"""
import asyncio
import subprocess
import sys
import time
import warnings

# Suppress async generator cleanup warnings
warnings.filterwarnings("ignore", message=".*asynchronous generator.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="mcp")

servers = []

def start_mcp_servers():
    """Start all MCP servers as background processes."""
    server_configs = [
        ("warranty", "src.servers.warranty.main", 8002),
        ("actions", "src.servers.actions.main", 8003),
    ]
    
    print("\n[*] Starting MCP Servers...")
    for name, module, port in server_configs:
        print(f"  Starting {name} on port {port}...")
        proc = subprocess.Popen(
            [sys.executable, "-m", module],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        servers.append(proc)
    
    time.sleep(2)
    print("  All servers started.\n")

def stop_mcp_servers():
    """Stop all MCP servers."""
    print("\n[*] Stopping MCP servers...")
    for proc in servers:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
    print("Done.")

async def interactive_session():
    """Run interactive session with the agent."""
    from src.agent import create_warranty_agent
    
    print("="*60)
    print("WARRANTY AGENT - INTERACTIVE TEST")
    print("="*60)
    print("\nType your messages and press Enter.")
    print("Type 'quit' or 'exit' to end the session.\n")
    
    agent = create_warranty_agent()
    
    while True:
        try:
            user_input = input("\n[YOU] > ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n[*] Ending session...")
                break
            
            if not user_input:
                continue
            
            print(f"\n[AGENT] Processing...\n")
            result = await agent.run(user_input)
            
            print("─"*60)
            print(result.text)
            print("─"*60)
            
        except KeyboardInterrupt:
            print("\n\n[*] Interrupted by user")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")
            continue

def main():
    """Main entry point."""
    start_mcp_servers()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(interactive_session())
    except KeyboardInterrupt:
        print("\n[*] Interrupted")
    finally:
        stop_mcp_servers()
        
        # Clean up
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

if __name__ == "__main__":
    main()
