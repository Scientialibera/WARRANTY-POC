"""
Test Report Generator

Generates nicely formatted test reports with detailed tool call information.
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """Represents a tool call made during a scenario."""
    tool_name: str
    arguments: Dict[str, Any]
    status: str
    result_summary: str
    result_data: Optional[Dict[str, Any]] = None


@dataclass
class Turn:
    """Represents a single turn in a scenario."""
    turn_number: int
    user_message: str
    bot_response: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    case_id: Optional[str] = None


@dataclass
class ScenarioResult:
    """Represents the result of a test scenario."""
    scenario_name: str
    description: str
    customer_id: str
    product_id: Optional[str]
    location: str
    turns: List[Turn] = field(default_factory=list)
    status: str = "PASS"
    case_id: Optional[str] = None


class TestReporter:
    """Generates formatted test reports."""
    
    def __init__(self):
        """Initialize the reporter."""
        self.scenarios: List[ScenarioResult] = []
    
    def add_scenario(self, scenario: ScenarioResult):
        """Add a scenario result."""
        self.scenarios.append(scenario)
    
    def generate_report(self, output_path: str):
        """Generate a formatted report and write to file."""
        lines = []
        
        # Header
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append("=" * 90)
        lines.append("WARRANTY ORCHESTRATOR - TEST REPORT")
        lines.append("=" * 90)
        lines.append(f"Generated: {timestamp}")
        lines.append(f"Total Scenarios: {len(self.scenarios)}")
        lines.append("")
        
        # Summary
        passed = sum(1 for s in self.scenarios if s.status == "PASS")
        failed = sum(1 for s in self.scenarios if s.status == "FAIL")
        lines.append("-" * 90)
        lines.append("TEST SUMMARY")
        lines.append("-" * 90)
        lines.append(f"Passed: {passed}/{len(self.scenarios)}")
        lines.append(f"Failed: {failed}/{len(self.scenarios)}")
        lines.append("")
        for i, scenario in enumerate(self.scenarios, 1):
            status_marker = "[PASS]" if scenario.status == "PASS" else "[FAIL]"
            lines.append(f"  {i}. {status_marker} {scenario.scenario_name}")
        lines.append("")
        lines.append("=" * 90)
        lines.append("")
        
        # Detailed scenarios
        for i, scenario in enumerate(self.scenarios, 1):
            lines.extend(self._format_scenario(scenario, i))
        
        # Footer
        lines.append("=" * 90)
        lines.append("END OF REPORT")
        lines.append("=" * 90)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        print(f"Test report generated: {output_path}")
    
    def _format_scenario(self, scenario: ScenarioResult, scenario_num: int) -> List[str]:
        """Format a single scenario."""
        lines = []
        product_info = scenario.product_id if scenario.product_id else "(None - Missing Info)"
        
        lines.append("-" * 90)
        lines.append(f"SCENARIO {scenario_num}: {scenario.scenario_name}")
        lines.append("-" * 90)
        lines.append(f"Status:      {scenario.status}")
        lines.append(f"Description: {scenario.description}")
        lines.append(f"Customer:    {scenario.customer_id}")
        lines.append(f"Product:     {product_info}")
        lines.append(f"Location:    {scenario.location}")
        lines.append(f"Case ID:     {scenario.case_id or 'N/A'}")
        lines.append(f"Turns:       {len(scenario.turns)}")
        lines.append("")
        
        # Format each turn
        for turn in scenario.turns:
            lines.extend(self._format_turn(turn))
        
        lines.append("")
        return lines
    
    def _format_turn(self, turn: Turn) -> List[str]:
        """Format a single turn with full tool call details."""
        lines = []
        lines.append(f"  TURN {turn.turn_number}")
        lines.append("  " + "-" * 86)
        
        # User message
        lines.append(f"  USER INPUT:")
        lines.append(f"    {turn.user_message}")
        lines.append("")
        
        # Tool calls - THIS IS THE KEY PART
        if turn.tool_calls:
            lines.append(f"  TOOL CALLS ({len(turn.tool_calls)}):")
            lines.append("")
            for i, tool_call in enumerate(turn.tool_calls, 1):
                lines.extend(self._format_tool_call(tool_call, i))
        else:
            lines.append("  TOOL CALLS: (none)")
            lines.append("")
        
        # Bot response
        lines.append(f"  BOT RESPONSE:")
        # Wrap long responses
        response_lines = self._wrap_text(turn.bot_response, 84)
        for line in response_lines:
            lines.append(f"    {line}")
        lines.append("")
        
        return lines
    
    def _format_tool_call(self, tool_call: ToolCall, number: int) -> List[str]:
        """Format a tool call with full arguments and results."""
        lines = []
        lines.append(f"    [{number}] TOOL: {tool_call.tool_name}")
        lines.append(f"        STATUS: {tool_call.status}")
        
        # Arguments - show ALL of them
        lines.append(f"        ARGUMENTS:")
        if tool_call.arguments:
            args_json = json.dumps(tool_call.arguments, indent=2, default=str)
            for line in args_json.split("\n"):
                lines.append(f"          {line}")
        else:
            lines.append(f"          (no arguments)")
        
        # Full result data - ALWAYS show everything
        lines.append(f"        RESULT:")
        if tool_call.result_data:
            result_json = json.dumps(tool_call.result_data, indent=2, default=str)
            for line in result_json.split("\n"):
                lines.append(f"          {line}")
        else:
            # Fallback to summary if no result_data
            lines.append(f"          {tool_call.result_summary}")
        
        lines.append("")
        return lines
    
    def _format_value(self, value: Any) -> str:
        """Format a value for display."""
        if isinstance(value, dict):
            return json.dumps(value, indent=2, default=str)
        elif isinstance(value, list):
            return json.dumps(value, default=str)
        elif isinstance(value, str) and "\n" in value:
            return value
        elif isinstance(value, str) and len(value) > 100:
            return value[:97] + "..."
        else:
            return str(value)
    
    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to a maximum width."""
        if not text:
            return ["(no response)"]
        
        lines = []
        for paragraph in text.split("\n"):
            if len(paragraph) <= width:
                lines.append(paragraph)
            else:
                words = paragraph.split()
                current_line = []
                current_length = 0
                
                for word in words:
                    if current_length + len(word) + 1 <= width:
                        current_line.append(word)
                        current_length += len(word) + 1
                    else:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                        current_length = len(word)
                
                if current_line:
                    lines.append(" ".join(current_line))
        
        return lines if lines else ["(empty)"]
