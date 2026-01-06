"""
Planner MCP Server

This MCP server provides a planning capability that returns structured plans
for the warranty workflow. The plans follow a strict contract and only use
approved step types.

Plan Step Types:
- ASK_USER_FOR_INFO: Request missing information from user
- CALL_TOOL: Execute a tool with specified arguments
- RETURN_ACTION: Return a control action (PROMPT_LOGIN, PROMPT_PRODUCT_REGISTRATION, etc.)
- RESPOND_TO_USER: Send a response message to the user

The planner enforces workflow constraints:
1. Warranty determination must happen before Salt/Heat branching
2. HEAT: Calculate charges before asking to proceed
3. HEAT: Ask to proceed before territory check
4. HEAT: Territory check before PayPal link generation
5. Decline path must log a reason
"""

import json
import sys
from typing import Any
from dataclasses import dataclass, asdict
from enum import Enum


class StepType(str, Enum):
    """Valid step types in a plan."""
    ASK_USER_FOR_INFO = "ASK_USER_FOR_INFO"
    CALL_TOOL = "CALL_TOOL"
    RETURN_ACTION = "RETURN_ACTION"
    RESPOND_TO_USER = "RESPOND_TO_USER"


class ActionType(str, Enum):
    """Valid action types for RETURN_ACTION steps."""
    PROMPT_LOGIN = "PROMPT_LOGIN"
    PROMPT_PRODUCT_REGISTRATION = "PROMPT_PRODUCT_REGISTRATION"
    CASE_COMPLETE = "CASE_COMPLETE"
    ESCALATE = "ESCALATE"


@dataclass
class PlanStep:
    """A single step in the execution plan."""
    step_type: str
    description: str
    tool_name: str | None = None
    tool_args: dict | None = None
    action_type: str | None = None
    required_fields: list[str] | None = None
    message: str | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = {"step_type": self.step_type, "description": self.description}
        if self.tool_name:
            result["tool_name"] = self.tool_name
        if self.tool_args:
            result["tool_args"] = self.tool_args
        if self.action_type:
            result["action_type"] = self.action_type
        if self.required_fields:
            result["required_fields"] = self.required_fields
        if self.message:
            result["message"] = self.message
        return result


def generate_plan(context: dict, user_message: str) -> dict:
    """
    Generate a structured plan based on the current context.
    
    This function implements the workflow logic and returns a plan
    that the orchestrator will execute step by step.
    
    Args:
        context: Current case context
        user_message: The user's latest message
        
    Returns:
        A dictionary with status, plan steps, and reasoning
    """
    steps: list[PlanStep] = []
    
    # Extract context values with defaults
    logged_in = context.get("logged_in", False)
    has_registered_products = context.get("has_registered_products", False)
    product_id = context.get("product_id") or context.get("serial_number")
    location = context.get("location", {})
    product_type = context.get("product_type")
    warranty_status = context.get("warranty_status", {})
    customer_decision = context.get("customer_decision")
    potential_charges = context.get("potential_charges")
    
    # Check for location completeness
    has_location = bool(location.get("zip") or (location.get("city") and location.get("state")))
    
    # STEP 1: Login Gate
    if not logged_in:
        steps.append(PlanStep(
            step_type=StepType.RETURN_ACTION,
            description="User must be logged in to proceed with warranty service",
            action_type=ActionType.PROMPT_LOGIN,
            message="Please log in to access warranty services. You can ask simple questions without logging in, but warranty claims require authentication."
        ))
        return _build_response(steps, "User not logged in - prompting for login")
    
    # STEP 2: Registration Gate
    if not has_registered_products:
        steps.append(PlanStep(
            step_type=StepType.RETURN_ACTION,
            description="User must have registered products to proceed",
            action_type=ActionType.PROMPT_PRODUCT_REGISTRATION,
            message="You don't have any registered products. Please register your product to access warranty services."
        ))
        return _build_response(steps, "No registered products - prompting for registration")
    
    # STEP 3: Collect Required Info
    missing_fields = []
    if not product_id:
        missing_fields.append("product_id")
    if not has_location:
        missing_fields.append("location (zip code or city/state)")
    
    if missing_fields:
        steps.append(PlanStep(
            step_type=StepType.ASK_USER_FOR_INFO,
            description="Collect missing information required for warranty processing",
            required_fields=missing_fields,
            message=f"To help you with your warranty request, I need the following information: {', '.join(missing_fields)}"
        ))
        return _build_response(steps, f"Missing required fields: {missing_fields}")
    
    # STEP 4: Determine Warranty + Product Type (if not already done)
    if not product_type or not warranty_status.get("active") is not None:
        steps.append(PlanStep(
            step_type=StepType.CALL_TOOL,
            description="Look up warranty record to determine product type and warranty status",
            tool_name="get_warranty_record",
            tool_args={"product_id": product_id}
        ))
        steps.append(PlanStep(
            step_type=StepType.RESPOND_TO_USER,
            description="Inform user of warranty lookup results",
            message="I've retrieved your warranty information. Let me explain your coverage..."
        ))
        return _build_response(steps, "Need to determine warranty status and product type")
    
    # STEP 5: Branch by Product Type
    if product_type == "SALT":
        return _generate_salt_plan(steps, context, warranty_status)
    elif product_type == "HEAT":
        return _generate_heat_plan(steps, context, warranty_status, customer_decision, potential_charges, user_message)
    else:
        # Unknown product type - this shouldn't happen
        steps.append(PlanStep(
            step_type=StepType.RESPOND_TO_USER,
            description="Handle unknown product type",
            message=f"I found an unexpected product type: {product_type}. Let me connect you with support."
        ))
        steps.append(PlanStep(
            step_type=StepType.RETURN_ACTION,
            description="Escalate unknown product type",
            action_type=ActionType.ESCALATE
        ))
        return _build_response(steps, f"Unknown product type: {product_type}")


def _generate_salt_plan(steps: list[PlanStep], context: dict, warranty_status: dict) -> dict:
    """Generate plan for SALT product path."""
    is_warranty_active = warranty_status.get("active", False)
    location = context.get("location", {})
    
    if not is_warranty_active:
        # Non-warranty SALT: Return service directory
        steps.append(PlanStep(
            step_type=StepType.CALL_TOOL,
            description="Get service directory for non-warranty SALT product",
            tool_name="get_service_directory",
            tool_args={"product_type": "SALT", "location": location}
        ))
        steps.append(PlanStep(
            step_type=StepType.RESPOND_TO_USER,
            description="Present service providers to customer",
            message="Your product is no longer under warranty. Here are authorized service providers in your area:"
        ))
        return _build_response(steps, "SALT non-warranty path - returning service directory")
    else:
        # Warranty SALT: Queue for service
        steps.append(PlanStep(
            step_type=StepType.CALL_TOOL,
            description="Route warranty case to SALT queue",
            tool_name="route_to_queue",
            tool_args={"queue": "WarrantySalt", "case_context": context, "priority": "normal"}
        ))
        steps.append(PlanStep(
            step_type=StepType.CALL_TOOL,
            description="Notify customer of next steps",
            tool_name="notify_next_steps",
            tool_args={
                "channel": "chat",
                "template_id": "warranty_queued",
                "context": {
                    "product_name": context.get("product_id"),
                    "estimated_response_time": "24-48 hours",
                    "next_action": "A warranty specialist will contact you"
                }
            }
        ))
        steps.append(PlanStep(
            step_type=StepType.RESPOND_TO_USER,
            description="Confirm case creation to customer",
            message="Your warranty claim has been submitted! A specialist will contact you within 24-48 hours."
        ))
        return _build_response(steps, "SALT warranty path - case queued for service")


def _generate_heat_plan(
    steps: list[PlanStep],
    context: dict,
    warranty_status: dict,
    customer_decision: str | None,
    potential_charges: float | None,
    user_message: str
) -> dict:
    """
    Generate plan for HEAT product path.
    
    STRICT ORDER:
    1. Calculate charges (MUST happen before asking to proceed)
    2. Ask user to proceed
    3. If declined: log reason
    4. If proceed: territory check
    5. If serviceable: PayPal link
    6. If not serviceable: service directory
    """
    location = context.get("location", {})
    product_id = context.get("product_id")
    
    # HEAT Step 1: Calculate charges (if not already done)
    if potential_charges is None:
        steps.append(PlanStep(
            step_type=StepType.CALL_TOOL,
            description="Calculate potential service charges based on warranty coverage",
            tool_name="calculate_charges",
            tool_args={
                "product_id": product_id,
                "product_type": "HEAT",
                "warranty_status": warranty_status,
                "location": location
            }
        ))
        steps.append(PlanStep(
            step_type=StepType.RESPOND_TO_USER,
            description="Present charges and ask for confirmation",
            message="Based on your warranty coverage, here are the potential charges. Would you like to proceed?"
        ))
        return _build_response(steps, "HEAT path - calculating charges")
    
    # HEAT Step 2: Handle customer decision
    if customer_decision is None or customer_decision == "PENDING":
        # Check if user's message indicates a decision
        user_lower = user_message.lower()
        if any(word in user_lower for word in ["yes", "proceed", "continue", "ok", "sure", "agree"]):
            # User wants to proceed
            customer_decision = "PROCEED"
        elif any(word in user_lower for word in ["no", "cancel", "stop", "decline", "don't", "dont"]):
            # User is declining
            customer_decision = "DECLINE"
        else:
            # Still waiting for decision
            steps.append(PlanStep(
                step_type=StepType.ASK_USER_FOR_INFO,
                description="Ask customer to confirm proceeding with service",
                required_fields=["proceed_confirmation"],
                message=f"The estimated charge for service is ${potential_charges:.2f}. Would you like to proceed? (Please reply Yes or No. If No, please let me know the reason.)"
            ))
            return _build_response(steps, "HEAT path - awaiting customer decision")
    
    # Handle DECLINE
    if customer_decision == "DECLINE":
        # Extract reason from user message if possible
        reason = user_message if len(user_message) > 10 else "Customer declined without specific reason"
        
        steps.append(PlanStep(
            step_type=StepType.CALL_TOOL,
            description="Log the reason for declining service",
            tool_name="log_decline_reason",
            tool_args={
                "reason": reason,
                "context": {
                    "case_id": context.get("case_id"),
                    "product_id": product_id,
                    "potential_charges": potential_charges,
                    "warranty_status": warranty_status
                }
            }
        ))
        steps.append(PlanStep(
            step_type=StepType.RESPOND_TO_USER,
            description="Acknowledge decline and offer alternatives",
            message="I understand. I've noted your decision. If you change your mind or have any questions, please don't hesitate to reach out. Is there anything else I can help you with?"
        ))
        return _build_response(steps, "HEAT path - customer declined, reason logged")
    
    # HEAT Step 3: Territory check (customer decided to PROCEED)
    territory_checked = context.get("territory_checked")
    territory_serviceable = context.get("territory_serviceable")
    
    if territory_checked is None:
        steps.append(PlanStep(
            step_type=StepType.CALL_TOOL,
            description="Check if location is in serviceable territory",
            tool_name="check_territory",
            tool_args={"location": location}
        ))
        return _build_response(steps, "HEAT path - checking territory")
    
    # HEAT Step 4: Handle based on territory result
    if not territory_serviceable:
        # Not serviceable - return service directory
        steps.append(PlanStep(
            step_type=StepType.CALL_TOOL,
            description="Get service directory for non-serviceable territory",
            tool_name="get_service_directory",
            tool_args={"product_type": "HEAT", "location": location}
        ))
        steps.append(PlanStep(
            step_type=StepType.RESPOND_TO_USER,
            description="Inform customer about service options",
            message="Unfortunately, your location is outside our direct service territory. Here are authorized service providers in your area who can help:"
        ))
        return _build_response(steps, "HEAT path - not serviceable, returning directory")
    
    # HEAT Step 5: Generate PayPal link (serviceable territory)
    steps.append(PlanStep(
        step_type=StepType.CALL_TOOL,
        description="Generate PayPal payment link for service charges",
        tool_name="generate_paypal_link",
        tool_args={
            "amount": potential_charges,
            "metadata": {
                "case_id": context.get("case_id"),
                "product_id": product_id,
                "description": "HEAT product service charge"
            }
        }
    ))
    steps.append(PlanStep(
        step_type=StepType.RESPOND_TO_USER,
        description="Provide payment link and next steps",
        message=f"Great! Please complete your payment of ${potential_charges:.2f} using the link below. Once payment is confirmed, we'll schedule your service appointment."
    ))
    return _build_response(steps, "HEAT path - payment link generated")


def _build_response(steps: list[PlanStep], reasoning: str) -> dict:
    """Build the standard response format."""
    return {
        "status": "ok",
        "data": {
            "plan": [step.to_dict() for step in steps],
            "step_count": len(steps),
            "reasoning": reasoning
        }
    }


# MCP Server Implementation
def handle_request(request: dict) -> dict:
    """Handle an MCP request."""
    method = request.get("method", "")
    request_id = request.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "warranty-planner",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "get_plan",
                        "description": "Generate a structured execution plan for the warranty workflow based on current context.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "context": {
                                    "type": "object",
                                    "description": "Current case context"
                                },
                                "user_message": {
                                    "type": "string",
                                    "description": "The latest message from the user"
                                }
                            },
                            "required": ["context", "user_message"]
                        }
                    }
                ]
            }
        }
    
    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name == "get_plan":
            context = arguments.get("context", {})
            user_message = arguments.get("user_message", "")
            result = generate_plan(context, user_message)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
    
    elif method == "notifications/initialized":
        # This is a notification, no response needed
        return None
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


def main():
    """Main entry point for the MCP server using STDIO transport."""
    import sys
    
    # Log to stderr to avoid breaking JSON-RPC on stdout
    sys.stderr.write("Planner MCP Server starting...\n")
    sys.stderr.flush()
    
    while True:
        try:
            # Read line from stdin
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            # Parse JSON-RPC request
            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                sys.stderr.write(f"JSON parse error: {e}\n")
                sys.stderr.flush()
                continue
            
            # Handle request
            response = handle_request(request)
            
            # Send response (skip for notifications)
            if response is not None:
                response_str = json.dumps(response)
                sys.stdout.write(response_str + "\n")
                sys.stdout.flush()
                
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
