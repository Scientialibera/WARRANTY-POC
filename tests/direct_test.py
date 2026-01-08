"""
Direct interactive CLI test - full control, see everything the orchestrator does.
"""
import asyncio
import subprocess
import sys
import time

async def main():
    """Interactive CLI chat with full visibility."""
    from src.agent import create_warranty_agent
    
    print("=" * 80)
    print("DIRECT INTERACTIVE WARRANTY AGENT TEST")
    print("=" * 80)
    print("\nStarting MCP servers...")
    
    # Start MCP servers
    servers = []
    try:
        warranty_proc = subprocess.Popen(
            ["python", "-m", "src.servers.warranty.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        servers.append(warranty_proc)
        
        actions_proc = subprocess.Popen(
            ["python", "-m", "src.servers.actions.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        servers.append(actions_proc)
        
        time.sleep(2)
        print("✓ MCP servers started\n")
        
        # Create agent
        print("Creating warranty agent...")
        agent = create_warranty_agent()
        print("✓ Agent ready\n")
        
        print("=" * 80)
        print("You can now chat with the agent. Type 'quit' to exit, 'NEW' to start fresh.")
        print("=" * 80)
        
        # Track conversation history
        from agent_framework import ChatMessage
        conversation = []
        
        while True:
            # Get user input
            user_input = input("\n[YOU] ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nExiting...")
                break
            
            if user_input.upper() == 'NEW':
                conversation = []
                print("\n" + "="*80)
                print("✨ STARTING NEW CONVERSATION - History cleared")
                print("="*80)
                continue
            
            if not user_input:
                continue
            
            # Add to conversation
            conversation.append(ChatMessage(role='user', text=user_input))
            
            print(f"\n{'='*80}")
            print("ORCHESTRATOR EXECUTION")
            print(f"{'='*80}")
            print(f"\n[DEBUG] Your input: {user_input}")
            print(f"[DEBUG] Conversation has {len(conversation)} messages")
            print(f"[DEBUG] Last message type: {type(conversation[-1])}")
            print(f"[DEBUG] Last message .text: {conversation[-1].text if hasattr(conversation[-1], 'text') else 'N/A'}")
            print()
            
            # Run agent
            try:
                result = await agent.run(conversation)
                
                # Show tool calls IMMEDIATELY
                print(f"\n[TOOL CALLS MADE BY ORCHESTRATOR]")
                if hasattr(result, 'raw_representation') and result.raw_representation:
                    raw = result.raw_representation
                    if hasattr(raw, 'messages') and raw.messages:
                        tool_count = 0
                        for message in raw.messages:
                            if hasattr(message, 'contents') and message.contents:
                                for content in message.contents:
                                    content_type = type(content).__name__
                                    if content_type == 'FunctionCallContent':
                                        tool_count += 1
                                        tool_name = getattr(content, 'name', 'unknown')
                                        args_str = getattr(content, 'arguments', '{}')
                                        
                                        import json
                                        try:
                                            args = json.loads(args_str) if isinstance(args_str, str) else args_str
                                        except:
                                            args = {"raw": str(args_str)}
                                        
                                        # Determine server
                                        if tool_name == 'get_plan':
                                            server = "PlannerAgent"
                                        elif tool_name == 'execute_python':
                                            server = "PythonExecutor"
                                        elif tool_name == 'get_warranty_terms':
                                            server = "Warranty MCP"
                                        elif tool_name in ['check_territory', 'get_service_directory', 'route_to_queue', 'generate_paypal_link', 'log_decline_reason']:
                                            server = "Actions MCP"
                                        elif 'code' in tool_name.lower() or 'interpreter' in tool_name.lower():
                                            server = "CodeInterpreter"
                                        else:
                                            server = "Unknown"
                                        
                                        print(f"  [{tool_count}] {server} → {tool_name}")
                                        print(f"      Arguments:")
                                        for key, value in args.items():
                                            print(f"        • {key}: {value}")
                        
                        if tool_count == 0:
                            print("  (No tool calls - direct response)")
                else:
                    print("  (No tool execution info available)")
                
                print(f"\n{'='*80}")
                
                # Add assistant messages to conversation
                if result.messages:
                    conversation.extend(result.messages)
                
                # Show response
                print(f"\n[AGENT] {result.text}")
                
            except Exception as e:
                print(f"\n[ERROR] {e}")
                import traceback
                traceback.print_exc()
        
    finally:
        # Stop servers
        print("\nStopping MCP servers...")
        for proc in servers:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except:
                proc.kill()
        print("✓ Servers stopped")


if __name__ == "__main__":
    asyncio.run(main())
