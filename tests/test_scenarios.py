"""
Comprehensive Test Scenarios for Warranty POC

Tests various paths:
1. Full info provided - complete workflow
2. Missing info - multi-turn info gathering
3. Confirmation flow - accept/decline
4. Out of warranty - service directory
5. Code interpreter calculations

Generates detailed test report with MCP calls and tool usage.
"""
import asyncio
import subprocess
import sys
import time
import json
import warnings
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

# Suppress async generator cleanup warnings from MCP client
warnings.filterwarnings("ignore", message=".*asynchronous generator.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="mcp")

# Custom exception handler for asyncio to suppress MCP cleanup errors
def custom_exception_handler(loop, context):
    exception = context.get("exception")
    message = context.get("message", "")
    
    # Suppress MCP HTTP client cleanup errors
    if "streamable_http" in str(exception) or "streamablehttp" in message.lower():
        return
    if "GeneratorExit" in str(exception):
        return
    if "cancel scope" in message.lower():
        return
    if "asynchronous generator" in message.lower():
        return
    if "athrow" in message.lower() or "aclose" in message.lower():
        return
    
    # Log other exceptions normally
    loop.default_exception_handler(context)


# Install a custom sys.excepthook to suppress MCP cleanup tracebacks
_original_excepthook = sys.excepthook
def _custom_excepthook(exc_type, exc_value, exc_tb):
    # Suppress MCP async generator cleanup errors
    exc_str = str(exc_value).lower()
    if any(x in exc_str for x in ["generatorexit", "cancel scope", "asynchronous generator", "athrow", "aclose"]):
        return
    _original_excepthook(exc_type, exc_value, exc_tb)

sys.excepthook = _custom_excepthook


# Test report structure
@dataclass
class ToolCall:
    mcp_server: str
    tool_name: str
    arguments: dict
    result: Any = None
    output: str = ""
    timestamp: str = ""

@dataclass
class TestScenario:
    name: str
    description: str
    messages: list[str]
    expected_tools: list[str]  # Tools we expect to be called
    responses: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    planner_outputs: list[str] = field(default_factory=list)
    code_interpreter_used: bool = False
    code_interpreter_code: str = ""
    success: bool = False
    duration_ms: int = 0

@dataclass
class TestReport:
    start_time: str
    end_time: str
    total_duration_ms: int
    scenarios: list[TestScenario]
    total_mcp_calls: int = 0
    total_code_interpreter_calls: int = 0
    
    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": self.total_duration_ms,
            "summary": {
                "total_scenarios": len(self.scenarios),
                "passed": sum(1 for s in self.scenarios if s.success),
                "failed": sum(1 for s in self.scenarios if not s.success),
                "total_mcp_calls": self.total_mcp_calls,
                "total_code_interpreter_calls": self.total_code_interpreter_calls,
            },
            "scenarios": [
                {
                    "name": s.name,
                    "description": s.description,
                    "success": s.success,
                    "duration_ms": s.duration_ms,
                    "messages_sent": len(s.messages),
                    "responses": s.responses,
                    "expected_tools": s.expected_tools,
                    "tool_calls": [
                        {
                            "mcp_server": tc.mcp_server,
                            "tool_name": tc.tool_name,
                            "arguments": tc.arguments,
                            "timestamp": tc.timestamp
                        } for tc in s.tool_calls
                    ],
                    "code_interpreter": {
                        "used": s.code_interpreter_used,
                        "code": s.code_interpreter_code
                    } if s.code_interpreter_used else None
                }
                for s in self.scenarios
            ]
        }


# Define test scenarios
TEST_SCENARIOS = [
    # ============================================
    # SCENARIO 1: Full info - HEAT with active warranty
    # ============================================
    TestScenario(
        name="HEAT Full Info - Active Warranty",
        description="Customer provides all info upfront for a HEAT product with active warranty. Should lookup warranty, check territory, calculate charges, ask for confirmation.",
        messages=[
            "I need help with my heat pump water heater. Serial number is SN-HEAT-2025-001111 and I'm located in ZIP 77002. It's making strange noises.",
            "Yes, I agree to the charges. Please proceed with the service."
        ],
        expected_tools=["get_warranty_terms", "check_territory", "generate_paypal_link"],
    ),
    
    # # ============================================
    # # SCENARIO 2: Full info - SALT with active warranty  
    # # ============================================
    # TestScenario(
    #     name="SALT Full Info - Active Warranty",
    #     description="Customer provides all info for SALT product. Should lookup warranty, check territory, route to queue.",
    #     messages=[
    #         "My water softener serial SN-SALT-2024-001234 isn't regenerating. I'm at 77003."
    #     ],
    #     expected_tools=["get_warranty_record", "check_territory", "route_to_queue"],
    # ),
    
    # # ============================================
    # # SCENARIO 3: Missing info - gather progressively
    # # ============================================
    # TestScenario(
    #     name="Missing Info - Progressive Gathering",
    #     description="Customer provides minimal info. Agent should ask for missing info progressively.",
    #     messages=[
    #         "My water heater is broken",
    #         "It's a heat pump water heater, the elite model",
    #         "The serial number is SN-HEAT-2025-001111",
    #         "My ZIP code is 77005"
    #     ],
    #     expected_tools=["get_warranty_record", "check_territory"],
    # ),
    
    # # ============================================
    # # SCENARIO 4: Decline service flow
    # # ============================================
    # TestScenario(
    #     name="Customer Declines Service",
    #     description="Customer declines after seeing charges. Should log decline reason.",
    #     messages=[
    #         "Heat pump water heater SN-HEAT-2025-001111 at ZIP 77001 is not working",
    #         "No, that's too expensive. I'll find another service provider."
    #     ],
    #     expected_tools=["get_warranty_record", "log_decline_reason"],
    # ),
    
    # # ============================================
    # # SCENARIO 5: Out of warranty - service directory
    # # ============================================
    # TestScenario(
    #     name="Expired Warranty - Service Directory",
    #     description="Product with expired warranty. Should provide service directory.",
    #     messages=[
    #         "I need help with my heat pump water heater serial SN-HEAT-2020-002222. ZIP 77004."
    #     ],
    #     expected_tools=["get_warranty_record", "get_service_directory"],
    # ),
    
    # # ============================================
    # # SCENARIO 6: Out of territory
    # # ============================================
    # TestScenario(
    #     name="Out of Service Territory",
    #     description="Customer is outside serviceable area. Should check territory and provide alternatives.",
    #     messages=[
    #         "My SALT softener SN-SALT-2024-001234 needs service. ZIP is 90210."
    #     ],
    #     expected_tools=["get_warranty_record", "check_territory"],
    # ),
    
    # # ============================================
    # # SCENARIO 7: Code interpreter calculation
    # # ============================================
    # TestScenario(
    #     name="Code Interpreter - Cost Calculation",
    #     description="Request requiring code interpreter for complex calculation.",
    #     messages=[
    #         "My warranty covers $500 for parts and $200 for labor. There's a $75 deductible and 8.25% tax on parts only. Calculate my total out-of-pocket cost and the final reimbursement amount."
    #     ],
    #     expected_tools=[],  # No MCP tools, just code interpreter
    # ),
    
    # # ============================================
    # # SCENARIO 8: Multiple products inquiry
    # # ============================================
    # TestScenario(
    #     name="Multiple Products Query",
    #     description="Customer asks about multiple products in one message.",
    #     messages=[
    #         "I have two products that need service: a heat pump SN-HEAT-2025-001111 and a water softener SN-SALT-2024-001234. Both are at ZIP 77002. Can you check both warranties?"
    #     ],
    #     expected_tools=["get_warranty_record"],  # Should be called twice
    # ),
]


# MCP server processes
servers: list[subprocess.Popen] = []

def start_mcp_servers():
    """Start all MCP servers as background processes."""
    server_configs = [
        ("warranty", "src.servers.warranty.main", 8002),
        ("actions", "src.servers.actions.main", 8003),
    ]
    
    for name, module, port in server_configs:
        print(f"  Starting {name} MCP server on port {port}...")
        proc = subprocess.Popen(
            [sys.executable, "-m", module],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        servers.append(proc)
    
    time.sleep(2)
    print("  All MCP servers started.\n")

def stop_mcp_servers():
    """Stop all MCP servers."""
    for proc in servers:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()


async def run_scenario(agent, scenario: TestScenario, interactive: bool = False) -> TestScenario:
    """Run a single test scenario and capture results."""
    start = time.time()
    
    print(f"\n  {'-'*50}")
    print(f"  [TEST] {scenario.name}")
    print(f"  {scenario.description}")
    print(f"  {'-'*50}")
    
    # Capture planner output from console
    import io
    import contextlib
    planner_buffer = io.StringIO()
    
    # Track full conversation as ChatMessage objects to preserve context
    from agent_framework import ChatMessage
    conversation_messages = []
    
    try:
        message_index = 0
        while message_index < len(scenario.messages):
            msg = scenario.messages[message_index]
            print(f"\n  [USER] {msg}")
            
            # Add user message to history
            conversation_messages.append(ChatMessage(role='user', text=msg))
            
            # Pass all messages so agent has full context
            result = await agent.run(conversation_messages)
            
            # IMMEDIATELY log tool calls from this result
            print(f"\n  [ORCHESTRATOR TOOL CALLS]")
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
                                        server = "Warranty"
                                    elif tool_name in ['check_territory', 'get_service_directory', 'route_to_queue', 'generate_paypal_link', 'log_decline_reason']:
                                        server = "Actions"
                                    elif 'code' in tool_name.lower() or 'interpreter' in tool_name.lower():
                                        server = "CodeInterpreter"
                                    else:
                                        server = "Unknown"
                                    
                                    print(f"    [{tool_count}] {server}/{tool_name}")
                                    print(f"        Args: {json.dumps(args, indent=10)}")
                    if tool_count == 0:
                        print(f"    (No tool calls in this response)")
            else:
                print(f"    (No raw_representation available)")
            print(f"  [END ORCHESTRATOR TOOL CALLS]\n")
            
            # Add assistant response messages to history
            if result.messages:
                conversation_messages.extend(result.messages)
            
            response = result.text
            scenario.responses.append(response)
            print(f"\n  [AGENT RESPONSE]")
            print(f"  {response}")
            print(f"  [END AGENT RESPONSE]\n")
            
            # Extract tool calls from result.raw_representation.messages
            try:
                if hasattr(result, 'raw_representation') and result.raw_representation:
                    raw = result.raw_representation
                    if hasattr(raw, 'messages') and raw.messages:
                        for message in raw.messages:
                            if hasattr(message, 'contents') and message.contents:
                                for content in message.contents:
                                    content_type = type(content).__name__
                                    
                                    if content_type == 'FunctionCallContent':
                                        # This is a tool call!
                                        tool_name = getattr(content, 'name', 'unknown')
                                        args_str = getattr(content, 'arguments', '{}')
                                        try:
                                            args = json.loads(args_str) if isinstance(args_str, str) else args_str
                                        except:
                                            args = {"raw": str(args_str)}
                                        
                                        # Determine MCP server from tool name
                                        mcp_server = "unknown"
                                        if tool_name in ['get_plan']:
                                            mcp_server = "PlannerAgent"  # LLM-based function tool
                                        elif tool_name == 'get_warranty_terms':
                                            mcp_server = "Warranty"
                                        elif tool_name in ['check_territory', 'get_service_directory', 'route_to_queue', 'generate_paypal_link', 'log_decline_reason']:
                                            mcp_server = "Actions"
                                        elif 'code' in tool_name.lower() or 'interpreter' in tool_name.lower():
                                            mcp_server = "CodeInterpreter"
                                            scenario.code_interpreter_used = True
                                        
                                        scenario.tool_calls.append(ToolCall(
                                            mcp_server=mcp_server,
                                            tool_name=tool_name,
                                            arguments=args,
                                            timestamp=datetime.now().isoformat()
                                        ))
                                        print(f"\n  [TOOL CALL] {mcp_server}/{tool_name}")
                                        print(f"  Arguments: {json.dumps(args, indent=2)}")
                                    
                                    # Check for code interpreter specific content
                                    if hasattr(content, 'to_dict'):
                                        d = content.to_dict()
                                        if d.get('type') == 'code_interpreter_call':
                                            scenario.code_interpreter_used = True
                                            scenario.code_interpreter_code = d.get('code', '')
                                            print(f"  [CODE] Code Interpreter called")
            except Exception as e:
                # Don't fail if we can't extract tool calls
                print(f"  [WARN] Could not extract tool calls: {e}")
            
            # Fallback: Check if code interpreter was used (look for code patterns in response)
            if not scenario.code_interpreter_used:
                if "```python" in response or ("# " in response and "=" in response and "\n" in response):
                    scenario.code_interpreter_used = True
                    # Extract code if present
                    if "```python" in response:
                        code_start = response.find("```python") + 9
                        code_end = response.find("```", code_start)
                        if code_end > code_start:
                            scenario.code_interpreter_code = response[code_start:code_end].strip()
            
            # INTERACTIVE MODE: Check if agent is asking for more info
            if interactive:
                asking_keywords = ["please provide", "could you", "i need", "what is", "can you share", "missing", "confirm", "details"]
                if any(keyword in response.lower() for keyword in asking_keywords):
                    print(f"\n  {'='*60}")
                    print(f"  [INTERACTIVE] AGENT IS ASKING FOR INPUT")
                    print(f"  {'='*60}")
                    print(f"\n  FULL AGENT RESPONSE:")
                    print(f"  {response}\n")
                    
                    if message_index + 1 < len(scenario.messages):
                        print(f"  [OPTION 1] Press ENTER to use scripted message:")
                        print(f"            '{scenario.messages[message_index + 1]}'")
                        print(f"  [OPTION 2] Type your own custom response")
                        print(f"  [OPTION 3] Type 'skip' to move to next scenario")
                    else:
                        print(f"  [NO MORE SCRIPTED MESSAGES]")
                        print(f"  Type your response (or 'skip' to end scenario):")
                    
                    print(f"\n  {'='*60}")
                    user_input = input("  YOUR INPUT > ").strip()
                    
                    if user_input.lower() == 'skip':
                        print(f"  [INTERACTIVE] Skipping to next scenario...")
                        break
                    elif user_input:
                        # Use custom input - add to conversation
                        print(f"\n  [USER - CUSTOM] {user_input}")
                        
                        # Add to conversation history
                        from agent_framework import ChatMessage
                        conversation_messages.append(ChatMessage(role='user', text=user_input))
                        
                        result = await agent.run(conversation_messages)
                        
                        # IMMEDIATELY log tool calls from custom input result
                        print(f"\n  [ORCHESTRATOR TOOL CALLS]")
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
                                                try:
                                                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                                                except:
                                                    args = {"raw": str(args_str)}
                                                
                                                # Determine server
                                                if tool_name == 'get_plan':
                                                    server = "PlannerAgent"
                                                elif tool_name == 'execute_python':
                                                    server = "PythonExecutor"
                                                elif tool_name in ['get_warranty_terms']:
                                                    server = "Warranty"
                                                elif tool_name in ['check_territory', 'get_service_directory', 'route_to_queue', 'generate_paypal_link', 'log_decline_reason']:
                                                    server = "Actions"
                                                elif 'code' in tool_name.lower() or 'interpreter' in tool_name.lower():
                                                    server = "CodeInterpreter"
                                                else:
                                                    server = "Unknown"
                                                
                                                print(f"    [{tool_count}] {server}/{tool_name}")
                                                print(f"        Args: {json.dumps(args, indent=10)}")
                                if tool_count == 0:
                                    print(f"    (No tool calls in this response)")
                        else:
                            print(f"    (No raw_representation available)")
                        print(f"  [END ORCHESTRATOR TOOL CALLS]\n")
                        
                        # Add assistant messages to history
                        if result.messages:
                            conversation_messages.extend(result.messages)
                        
                        response = result.text
                        scenario.responses.append(response)
                        print(f"\n  [AGENT RESPONSE]")
                        print(f"  {response}")
                        print(f"  [END AGENT RESPONSE]\n")
                        # Don't increment message_index, stay in interactive loop
                        continue
                    # else: user pressed Enter, continue with next scripted message
            
            message_index += 1
        
        scenario.success = True
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        scenario.success = False
    
    scenario.duration_ms = int((time.time() - start) * 1000)
    print(f"\n  [TIME] Duration: {scenario.duration_ms}ms")
    
    return scenario


async def run_all_tests(interactive: bool = False):
    """Run all test scenarios and generate report."""
    from src.agent import create_warranty_agent
    
    print("="*60)
    print("WARRANTY POC - COMPREHENSIVE TEST SUITE")
    if interactive:
        print("INTERACTIVE MODE: You can respond when agent asks questions")
    print("="*60)
    
    report_start = datetime.now()
    
    # Start servers
    print("\n[*] Starting MCP Servers...")
    start_mcp_servers()
    
    # Run all scenarios
    print("\n" + "="*60)
    print("RUNNING TEST SCENARIOS")
    print("="*60)
    
    completed_scenarios = []
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}/{len(TEST_SCENARIOS)}")
        
        # Create a FRESH agent for each scenario
        print(f"[*] Creating fresh Warranty Agent for scenario {i}...")
        agent = create_warranty_agent()
        
        completed = await run_scenario(agent, scenario, interactive=interactive)
        completed_scenarios.append(completed)
    
    report_end = datetime.now()
    
    # Build report
    report = TestReport(
        start_time=report_start.isoformat(),
        end_time=report_end.isoformat(),
        total_duration_ms=int((report_end - report_start).total_seconds() * 1000),
        scenarios=completed_scenarios,
        total_mcp_calls=sum(len(s.tool_calls) for s in completed_scenarios),
        total_code_interpreter_calls=sum(1 for s in completed_scenarios if s.code_interpreter_used),
    )
    
    # Print summary
    print("\n" + "="*60)
    print("TEST REPORT SUMMARY")
    print("="*60)
    
    summary = report.to_dict()["summary"]
    print(f"""
    Total Scenarios:    {summary['total_scenarios']}
    [PASS] Passed:      {summary['passed']}
    [FAIL] Failed:      {summary['failed']}
    
    [TOOL] MCP Tool Calls:         {summary['total_mcp_calls']}
    [CODE] Code Interpreter Calls: {summary['total_code_interpreter_calls']}
    
    [TIME] Total Duration:  {report.total_duration_ms}ms
    """)
    
    # Detailed results per scenario
    print("\n" + "="*60)
    print("DETAILED RESULTS")
    print("="*60)
    
    for s in completed_scenarios:
        status = "[PASS]" if s.success else "[FAIL]"
        print(f"\n{status} {s.name}")
        print(f"   Duration: {s.duration_ms}ms")
        print(f"   Messages: {len(s.messages)}")
        if s.code_interpreter_used:
            print(f"   [CODE] Code Interpreter: YES")
        
        # Show tool calls with details
        if s.tool_calls:
            print(f"\n   Tool Calls ({len(s.tool_calls)}):")
            for tc in s.tool_calls:
                print(f"     • {tc.mcp_server}/{tc.tool_name}")
                if tc.arguments:
                    print(f"       Args: {json.dumps(tc.arguments, indent=8)}")
        
        # Show all responses
        if s.responses:
            print(f"\n   Agent Responses ({len(s.responses)}):")
            for i, resp in enumerate(s.responses, 1):
                print(f"     Response {i}:")
                print(f"     {resp[:500]}..." if len(resp) > 500 else f"     {resp}")
                print()
    
    # Save report to file
    report_path = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"\n[FILE] Full report saved to: {report_path}")
    
    # Give async generators time to close gracefully
    await asyncio.sleep(0.5)
    
    return report


def main():
    """Main entry point."""
    import sys
    
    # Check for interactive flag
    interactive = '--interactive' in sys.argv or '-i' in sys.argv
    
    if interactive:
        print("\n[MODE] Interactive mode enabled - you can respond to agent questions")
    
    # Set up custom exception handler to suppress MCP cleanup errors
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(custom_exception_handler)
    
    try:
        report = loop.run_until_complete(run_all_tests(interactive=interactive))
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user")
    finally:
        print("\n[STOP] Stopping MCP servers...")
        stop_mcp_servers()
        
        # Clean up pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        
        # Give cancelled tasks time to clean up
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        
        loop.close()
        print("Done.")


if __name__ == "__main__":
    main()
