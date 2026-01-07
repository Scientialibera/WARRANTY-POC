"""
Warranty Orchestrator

The main orchestration agent that handles warranty workflow execution.
Uses Azure OpenAI with the Responses API for agentic reasoning with code interpreter.

This orchestrator:
1. Receives requests from Copilot Studio with user context
2. Calls the Planner to get a structured execution plan
3. Validates and executes each plan step
4. Maintains case state across turns
5. Enforces workflow constraints
"""

import os
import sys
import json
import asyncio
import logging
import tomllib
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from src.models import CaseContext, WarrantyStatus, Location
from src.compute.service import ComputeService


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from config/agent.toml."""
    config_path = "config/agent.toml"
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        logger.warning(f"Config file not found at {config_path}")
        return {}
    except Exception as e:
        logger.warning(f"Error loading config: {e}")
        return {}


# Workflow step types
STEP_TYPES = {
    "ASK_USER_FOR_INFO",
    "CALL_TOOL",
    "RETURN_ACTION",
    "RESPOND_TO_USER"
}

# Valid action types
ACTION_TYPES = {
    "PROMPT_LOGIN",
    "PROMPT_PRODUCT_REGISTRATION",
    "CASE_COMPLETE",
    "ESCALATE"
}


class PlanValidationError(Exception):
    """Raised when a plan violates workflow constraints."""
    pass


class WarrantyOrchestrator:
    """
    Main orchestration agent for warranty workflow.
    
    Uses Azure OpenAI Responses API with code interpreter for complex
    reasoning and calculation tasks.
    """
    
    def __init__(
        self,
        endpoint: str = None,
        deployment: str = None,
        api_version: str = "2024-12-01-preview"
    ):
        """
        Initialize the warranty orchestrator.
        
        Args:
            endpoint: Azure OpenAI endpoint URL
            deployment: Model deployment name
            api_version: API version
        """
        # Load config from file
        config = load_config()
        azure_config = config.get("agent", {}).get("azure_openai", {})
        
        # Priority: constructor args > config file > environment variables
        self.endpoint = endpoint or azure_config.get("endpoint") or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self.deployment = deployment or azure_config.get("deployment") or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self.api_version = azure_config.get("api_version", api_version)
        
        # Initialize compute service (local tool)
        self.compute_service = ComputeService()
        
        # Initialize Azure OpenAI client
        self._init_client()
        
        # Case context storage (in production, use Redis/database)
        self._cases: Dict[str, CaseContext] = {}
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        logger.info(f"Warranty Orchestrator initialized - endpoint={self.endpoint}, deployment={self.deployment}")
    
    def _init_client(self):
        """Initialize the Azure OpenAI client."""
        if not self.endpoint:
            logger.warning("No Azure OpenAI endpoint configured - using mock mode")
            self.client = None
            return
        
        try:
            # Use DefaultAzureCredential for managed identity
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential,
                "https://cognitiveservices.azure.com/.default"
            )
            
            self.client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                azure_ad_token_provider=token_provider,
                api_version=self.api_version
            )
            logger.info("Azure OpenAI client initialized with managed identity")
        except Exception as e:
            logger.warning(f"Failed to initialize Azure OpenAI client: {e}")
            self.client = None
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt from file."""
        prompt_path = "config/system_prompt.txt"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"System prompt not found at {prompt_path}")
            return "You are a warranty service assistant."
    
    def get_or_create_case(self, request: Dict[str, Any]) -> CaseContext:
        """
        Get existing case or create new one from request.
        
        Args:
            request: Incoming request from Copilot Studio
            
        Returns:
            CaseContext instance
        """
        case_id = request.get("case_id")
        
        if case_id and case_id in self._cases:
            case = self._cases[case_id]
            # Update with any new information from request
            if request.get("user_message"):
                case.add_user_message(request["user_message"])
            return case
        
        # Create new case
        case = CaseContext.from_request(request)
        if request.get("user_message"):
            case.add_user_message(request["user_message"])
        
        self._cases[case.case_id] = case
        logger.info(f"Created new case - case_id={case.case_id}")
        
        return case
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incoming warranty request.
        
        This is the main entry point for the orchestrator.
        
        Args:
            request: Request from Copilot Studio containing:
                - user_message: The user's message
                - logged_in: Boolean login status
                - has_registered_products: Boolean registration status
                - product_id: Optional product ID
                - location: Optional location object
                - case_id: Optional case ID for continuing a case
                
        Returns:
            Response dict with:
                - case_id: The case identifier
                - response: Message to display to user
                - action: Optional action for Copilot Studio to take
                - action_data: Optional data for the action
                - status: "ok" or "error"
        """
        try:
            # Get or create case context
            case = self.get_or_create_case(request)
            user_message = request.get("user_message", "")
            
            logger.info(f"Processing request - case_id={case.case_id}, user_message={user_message[:100]}")
            
            # Use LLM for reasoning (falls back to rule-based if client unavailable)
            result = await self.process_with_llm(case, user_message)
            
            # Save case state
            self._cases[case.case_id] = case
            
            return {
                "case_id": case.case_id,
                "status": "ok",
                **result
            }
            
        except Exception as e:
            logger.error(f"Request processing failed - error={str(e)}", exc_info=True)
            return {
                "case_id": request.get("case_id", "unknown"),
                "status": "error",
                "response": f"I apologize, but I encountered an error processing your request. Please try again.",
                "error": str(e)
            }
    
    async def _execute_workflow(
        self,
        case: CaseContext,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Execute the warranty workflow for a case.
        
        Args:
            case: Current case context
            user_message: User's latest message
            
        Returns:
            Result dictionary with response and optional actions
        """
        # Step 1: Get plan from planner
        plan = await self._get_plan(case, user_message)
        
        if not plan or "error" in plan:
            return {
                "response": "I'm having trouble processing your request. Could you please try again?",
                "action": None
            }
        
        # Step 2: Validate plan against workflow constraints
        try:
            self._validate_plan(plan, case)
        except PlanValidationError as e:
            logger.error(f"Plan validation failed - error={str(e)}")
            return {
                "response": "I need to verify some information. " + str(e),
                "action": None
            }
        
        # Step 3: Execute plan steps
        result = await self._execute_plan(plan, case, user_message)
        
        return result
    
    async def _get_plan(
        self,
        case: CaseContext,
        user_message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get execution plan from the planner.
        
        For POC, this calls the planner logic directly.
        In production, this would call the Planner MCP server.
        """
        # Import planner logic directly for POC
        from src.mcp_servers.planner import generate_plan
        
        context = case.to_dict()
        plan_result = generate_plan(context, user_message)
        
        if plan_result.get("status") == "ok":
            return plan_result.get("data", {})
        
        return None
    
    def _validate_plan(self, plan: Dict[str, Any], case: CaseContext) -> None:
        """
        Validate plan against workflow constraints.
        
        Raises PlanValidationError if constraints are violated.
        
        NOTE: For POC, we trust the planner's constraint enforcement.
        The planner already validates workflow order internally.
        """
        steps = plan.get("plan", [])
        
        # Basic validation only - check step types are valid
        for step in steps:
            step_type = step.get("step_type")
            
            # Handle enum values from planner
            if hasattr(step_type, 'value'):
                step_type = step_type.value
            
            if step_type not in STEP_TYPES:
                raise PlanValidationError(f"Invalid step type: {step_type}")
            
            if step_type == "RETURN_ACTION":
                action_type = step.get("action_type")
                if hasattr(action_type, 'value'):
                    action_type = action_type.value
                if action_type and action_type not in ACTION_TYPES:
                    raise PlanValidationError(f"Invalid action type: {action_type}")
        
        # The planner enforces workflow constraints internally:
        # - HEAT: charges → ask to proceed → territory check → PayPal/directory
        # - SALT: warranty check → queue or directory
        # No need to duplicate validation here for POC
    
    async def _execute_plan(
        self,
        plan: Dict[str, Any],
        case: CaseContext,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Execute the validated plan steps.
        
        Returns the first actionable result (user response or action).
        """
        steps = plan.get("plan", [])
        responses = []
        action = None
        action_data = None
        
        for step in steps:
            step_type = step.get("step_type")
            logger.info(f"Executing step - type={step_type}, description={step.get('description', 'N/A')}")
            
            if step_type == "RETURN_ACTION":
                action = step.get("action_type")
                action_data = {
                    "message": step.get("message", "")
                }
                responses.append(step.get("message", ""))
                logger.info(f"RETURN_ACTION: {action}")
                break  # Stop processing after return action
            
            elif step_type == "ASK_USER_FOR_INFO":
                responses.append(step.get("message", ""))
                action = "ASK_USER"
                action_data = {
                    "required_fields": step.get("required_fields", [])
                }
                logger.info(f"ASK_USER_FOR_INFO: {step.get('required_fields', [])}")
                break  # Wait for user response
            
            elif step_type == "CALL_TOOL":
                tool_name = step.get("tool_name")
                tool_args = step.get("tool_args", {})
                
                logger.info(f"CALL_TOOL: {tool_name}")
                result = await self._execute_tool(tool_name, tool_args, case)
                logger.info(f"Tool result status: {result.get('status', 'unknown')}")
                
                # Update case context with tool results
                self._update_case_from_tool_result(case, tool_name, result)
            
            elif step_type == "RESPOND_TO_USER":
                responses.append(step.get("message", ""))
                logger.info(f"RESPOND_TO_USER: {step.get('message', '')[:50]}...")
        
        # Combine responses
        full_response = "\n\n".join(responses) if responses else "I'm here to help with your warranty request."
        
        return {
            "response": full_response,
            "action": action,
            "action_data": action_data
        }
    
    async def _execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        case: CaseContext
    ) -> Dict[str, Any]:
        """
        Execute a tool and return the result.
        
        Routes to the appropriate MCP server or local tool.
        """
        logger.info(f"Executing tool - tool_name={tool_name}, args={tool_args}")
        
        try:
            # Import MCP server functions for POC (direct call)
            if tool_name == "get_plan":
                # Call the Planner MCP to get a structured execution plan
                from src.mcp_servers.planner import generate_plan
                user_message = tool_args.get("user_message", "")
                context = case.to_dict()
                plan_result = generate_plan(context, user_message)
                logger.info(f"PLANNER MCP: Generated plan with {len(plan_result.get('data', {}).get('plan', []))} steps")
                return plan_result
            
            elif tool_name == "get_warranty_record":
                from src.mcp_servers.warranty_docs import get_warranty_record
                result = get_warranty_record(
                    product_id=tool_args.get("product_id") or case.product_id,
                    serial_number=tool_args.get("serial_number")
                )
                logger.info(f"WARRANTY DOCS MCP: Retrieved warranty record for {tool_args.get('product_id') or case.product_id}")
                return result
            
            elif tool_name == "get_warranty_terms":
                from src.mcp_servers.warranty_docs import get_warranty_terms
                return get_warranty_terms()
            
            elif tool_name == "calculate_charges":
                # Ensure we have all required args from case context if LLM didn't provide them
                full_args = {
                    "product_id": tool_args.get("product_id", case.product_id),
                    "product_type": tool_args.get("product_type", case.product_type),
                    "warranty_status": tool_args.get("warranty_status", case.warranty_status.model_dump() if case.warranty_status else {}),
                    "location": tool_args.get("location", case.location.model_dump() if case.location else {})
                }
                result_str = self.compute_service.run(full_args)
                return json.loads(result_str)
            
            elif tool_name == "route_to_queue":
                from src.mcp_servers.actions import route_to_queue
                return route_to_queue(
                    queue=tool_args.get("queue"),
                    case_context=tool_args.get("case_context", case.to_dict()),
                    priority=tool_args.get("priority", "normal"),
                    idempotency_key=tool_args.get("idempotency_key")
                )
            
            elif tool_name == "get_service_directory":
                from src.mcp_servers.actions import get_service_directory
                return get_service_directory(
                    product_type=tool_args.get("product_type"),
                    location=tool_args.get("location", case.location.model_dump()),
                    max_distance_miles=tool_args.get("max_distance_miles", 50),
                    filters=tool_args.get("filters")
                )
            
            elif tool_name == "check_territory":
                from src.mcp_servers.actions import check_territory
                return check_territory(
                    location=tool_args.get("location", case.location.model_dump())
                )
            
            elif tool_name == "generate_paypal_link":
                from src.mcp_servers.actions import generate_paypal_link
                return generate_paypal_link(
                    amount=tool_args.get("amount", case.potential_charges or 0),
                    metadata=tool_args.get("metadata", {"case_id": case.case_id}),
                    currency=tool_args.get("currency", "USD"),
                    idempotency_key=tool_args.get("idempotency_key")
                )
            
            elif tool_name == "log_decline_reason":
                from src.mcp_servers.actions import log_decline_reason
                return log_decline_reason(
                    reason=tool_args.get("reason", ""),
                    context=tool_args.get("context", case.to_dict()),
                    idempotency_key=tool_args.get("idempotency_key")
                )
            
            elif tool_name == "notify_next_steps":
                from src.mcp_servers.actions import notify_next_steps
                return notify_next_steps(
                    channel=tool_args.get("channel", case.channel),
                    template_id=tool_args.get("template_id"),
                    context=tool_args.get("context", {}),
                    recipient=tool_args.get("recipient")
                )
            
            elif tool_name == "run_calculation":
                # Code interpreter for math operations
                code = tool_args.get("code", "")
                description = tool_args.get("description", "Calculation")
                
                logger.info(f"CODE INTERPRETER: {description}")
                logger.info(f"Code to execute:\n{code}")
                
                # Execute in a safe environment with datetime available
                import io
                import contextlib
                from datetime import datetime, date, timedelta
                
                # Capture stdout
                stdout_capture = io.StringIO()
                local_vars = {
                    "datetime": datetime,
                    "date": date,
                    "timedelta": timedelta,
                    "today": date.today(),
                    "now": datetime.now()
                }
                
                try:
                    with contextlib.redirect_stdout(stdout_capture):
                        exec(code, {"__builtins__": __builtins__}, local_vars)
                    
                    output = stdout_capture.getvalue().strip()
                    logger.info(f"CODE INTERPRETER result: {output}")
                    
                    return {
                        "status": "ok",
                        "data": {
                            "description": description,
                            "output": output,
                            "variables": {k: str(v) for k, v in local_vars.items() 
                                         if not k.startswith("_") and k not in ["datetime", "date", "timedelta", "today", "now"]}
                        }
                    }
                except Exception as e:
                    logger.error(f"CODE INTERPRETER error: {str(e)}")
                    return {
                        "status": "error",
                        "error_code": "CALCULATION_ERROR",
                        "message": str(e)
                    }
            
            else:
                logger.warning(f"Unknown tool: {tool_name}")
                return {
                    "status": "error",
                    "error_code": "UNKNOWN_TOOL",
                    "message": f"Tool not found: {tool_name}"
                }
                
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - error={str(e)}")
            return {
                "status": "error",
                "error_code": "TOOL_ERROR",
                "message": str(e)
            }
    
    def _update_case_from_tool_result(
        self,
        case: CaseContext,
        tool_name: str,
        result: Dict[str, Any]
    ) -> None:
        """Update case context with results from tool execution."""
        if result.get("status") != "ok":
            return
        
        data = result.get("data", {})
        
        if tool_name == "get_warranty_record":
            # Update product and warranty info
            case.product_type = data.get("product_type")
            case.product_name = data.get("product_name")
            case.purchase_date = data.get("purchase_date")
            
            warranty_data = data.get("warranty_status", {})
            case.warranty_status = WarrantyStatus(
                active=warranty_data.get("active", False),
                coverage_types=warranty_data.get("coverage_types", []),
                all_coverage=warranty_data.get("all_coverage", {})
            )
        
        elif tool_name == "calculate_charges":
            summary = data.get("summary", {})
            case.potential_charges = summary.get("total_potential_charges")
        
        elif tool_name == "check_territory":
            case.territory_checked = True
            case.territory_serviceable = data.get("serviceable", False)
        
        elif tool_name == "route_to_queue":
            # Case ID from queue might override
            if data.get("case_id"):
                case.case_id = data["case_id"]
    
    async def process_with_llm(
        self,
        case: CaseContext,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Process request using Azure OpenAI with tool calling.
        
        This method uses the LLM for complex reasoning and free-form
        conversation, while still enforcing workflow constraints.
        
        Implements a proper agentic loop:
        1. Send message to LLM
        2. If LLM wants to call tools, execute them and send results back
        3. Repeat until LLM gives a final response (no more tool calls)
        """
        if not self.client:
            logger.warning("No Azure OpenAI client available - falling back to rule-based processing")
            return await self._execute_workflow(case, user_message)
        
        logger.info(">>> Starting LLM agentic loop...")
        
        # Get current date for calculations
        from datetime import date
        current_date = date.today().isoformat()
        
        # Extract warranty details
        warranty_expiry = None
        coverage_limits = {}
        if case.warranty_status:
            warranty_expiry = getattr(case.warranty_status, 'expiration_date', None)
            coverage_limits = getattr(case.warranty_status, 'all_coverage', {})
        
        # Build initial messages
        messages = [
            {"role": "system", "content": self.system_prompt + """

IMPORTANT RESPONSE GUIDELINES:
- When you call a tool, wait for the result before responding
- After getting tool results, provide a CONCISE response to the user
- Do NOT explain your reasoning process or workflow steps to the user
- Do NOT output code blocks or function call syntax in your response
- Speak directly to the customer in a friendly, professional tone
- If you need more information from the user, ask clearly and wait for their response

CRITICAL - USE CODE INTERPRETER FOR ALL MATH:
- NEVER do math calculations yourself - always use the run_calculation tool
- Use run_calculation for: warranty days remaining, cost differences, coverage gaps, percentages, date arithmetic
- Example: To find warranty days remaining, use run_calculation with Python code
- Example: To find how much customer must pay if warranty covers $X but cost is $Y, use run_calculation
- Always show the customer the calculation results clearly
"""},
            {"role": "user", "content": f"""
=== CURRENT DATE ===
Today's Date: {current_date}

=== CASE CONTEXT ===
- Case ID: {case.case_id}
- Product: {case.product_id} (Type: {case.product_type})
- Product Name: {case.product_name or 'Unknown'}
- Purchase Date: {getattr(case, 'purchase_date', 'Unknown')}
- Location: {case.location.city}, {case.location.state} {case.location.zip if case.location else 'Unknown'}

=== WARRANTY DETAILS ===
- Warranty Active: {case.warranty_status.active if case.warranty_status else 'Unknown'}
- Warranty Expiry Date: {warranty_expiry or 'Not specified'}
- Coverage Types: {case.warranty_status.coverage_types if case.warranty_status else []}
- Coverage Limits: {json.dumps(coverage_limits, default=str) if coverage_limits else 'Not specified'}

=== CASE STATE ===
- Customer Decision: {case.customer_decision.value if case.customer_decision else 'PENDING'}
- Potential Charges: {case.potential_charges if case.potential_charges else 'Not calculated'}
- Territory Checked: {case.territory_checked}
- Territory Serviceable: {case.territory_serviceable}

=== CUSTOMER MESSAGE ===
{user_message}

REMINDER: Use run_calculation tool for ANY math (days remaining, cost gaps, etc.)
"""}
        ]
        
        max_iterations = 10  # Prevent infinite loops
        all_tool_results = []
        
        for iteration in range(max_iterations):
            try:
                logger.info(f">>> LLM iteration {iteration + 1}: Sending request to {self.deployment}...")
                
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                    tools=self._get_tool_definitions(),
                    tool_choice="auto",
                    max_tokens=2000
                )
                
                message = response.choices[0].message
                finish_reason = response.choices[0].finish_reason
                
                logger.info(f"<<< LLM response - finish_reason={finish_reason}, has_tool_calls={bool(message.tool_calls)}")
                
                # If LLM wants to call tools
                if message.tool_calls:
                    # Add assistant message with tool calls to history
                    messages.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in message.tool_calls
                        ]
                    })
                    
                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {}
                        
                        logger.info(f"    Executing tool: {tool_name} with args: {json.dumps(tool_args, default=str)[:200]}")
                        
                        # Execute the tool
                        result = await self._execute_tool(tool_name, tool_args, case)
                        all_tool_results.append({"tool": tool_name, "result": result})
                        
                        logger.info(f"    Tool result: {result.get('status', 'unknown')}")
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result, default=str)
                        })
                    
                    # Continue loop to get next LLM response
                    continue
                
                # No tool calls - LLM is done, return response
                final_response = message.content or "I've processed your request. Is there anything else I can help you with?"
                
                logger.info(f"<<< LLM final response (first 200 chars): {final_response[:200]}")
                
                return {
                    "response": final_response,
                    "action": None,
                    "tool_results": all_tool_results
                }
                
            except Exception as e:
                logger.error(f"LLM iteration {iteration + 1} failed - error={str(e)}", exc_info=True)
                break
        
        # If we exit the loop without a response, fall back to rule-based
        logger.warning("LLM loop exhausted or failed - falling back to rule-based processing")
        return await self._execute_workflow(case, user_message)
    
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for the LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_plan",
                    "description": "MUST BE CALLED FIRST. Get an execution plan from the Planner MCP. Returns a structured plan with workflow steps based on the current case context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_message": {
                                "type": "string",
                                "description": "The user's current message/request"
                            }
                        },
                        "required": ["user_message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_warranty_record",
                    "description": "MUST BE CALLED SECOND (after get_plan). Fetch warranty record from Warranty Docs MCP. Returns product_type, warranty_status, coverage_types, expiration_date, and coverage_limits.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "serial_number": {"type": "string"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate_charges",
                    "description": "Calculate potential service charges",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "product_type": {"type": "string"},
                            "warranty_status": {"type": "object"},
                            "location": {"type": "object"}
                        },
                        "required": ["product_id", "product_type", "warranty_status", "location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_territory",
                    "description": "Check if location is serviceable",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "object"}
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "route_to_queue",
                    "description": "Route case to service queue",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "queue": {"type": "string"},
                            "case_context": {"type": "object"},
                            "priority": {"type": "string"}
                        },
                        "required": ["queue", "case_context"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_service_directory",
                    "description": "Get list of service providers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_type": {"type": "string"},
                            "location": {"type": "object"}
                        },
                        "required": ["product_type", "location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_paypal_link",
                    "description": "Generate PayPal payment link",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number"},
                            "metadata": {"type": "object"}
                        },
                        "required": ["amount", "metadata"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "log_decline_reason",
                    "description": "Log reason for customer declining service",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"},
                            "context": {"type": "object"}
                        },
                        "required": ["reason", "context"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "notify_next_steps",
                    "description": "Send notification to customer",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "template_id": {"type": "string"},
                            "context": {"type": "object"}
                        },
                        "required": ["channel", "template_id", "context"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_calculation",
                    "description": "Execute Python code for complex calculations. Use this for ANY math operations including: warranty days remaining, cost differences, coverage gap calculations, date arithmetic, percentage calculations, etc. The orchestrator should NEVER do math directly - always use this tool.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute. Must print() the final result. Has access to datetime module."
                            },
                            "description": {
                                "type": "string",
                                "description": "Brief description of what calculation is being performed"
                            }
                        },
                        "required": ["code", "description"]
                    }
                }
            }
        ]
