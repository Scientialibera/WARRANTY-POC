"""Actions MCP Server - FastMCP HTTP"""
from fastmcp import FastMCP
from datetime import datetime
import uuid
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.servers.auth_middleware import OAuth2TokenValidator, require_auth

mcp = FastMCP("warranty-actions")

# Check if authentication is enabled
ENABLE_AUTH = os.environ.get("MCP_AUTHORIZATION", "false").lower() == "true"
AUTH_VALIDATOR = None

if ENABLE_AUTH:
    AUTH_VALIDATOR = OAuth2TokenValidator(
        audience=os.environ.get("ACTIONS_AUDIENCE", "api://actions-mcp-server"),
        token_validation_uri=os.environ.get("ACTIONS_TOKEN_VALIDATION_URI"),
        required_role=os.environ.get("ACTIONS_REQUIRED_ROLE", "Warranty.Actions"),
        tenant_id=os.environ.get("ENTRA_TENANT_ID")
    )
    print(f"[AUTH] OAuth 2.1 authentication ENABLED for actions server")
    print(f"[AUTH] Required audience: {AUTH_VALIDATOR.audience}")
    print(f"[AUTH] Required role: {AUTH_VALIDATOR.required_role}")
else:
    print("[AUTH] Authentication DISABLED (local development mode)")

# Service providers
PROVIDERS = {
    "SALT": [
        {"id": "SP-001", "name": "AquaPure Service Co.", "phone": "(713) 555-0101", "address": "123 Water St, Houston, TX"},
        {"id": "SP-002", "name": "SoftWater Solutions", "phone": "(713) 555-0202", "address": "456 Mineral Ave, Houston, TX"},
    ],
    "HEAT": [
        {"id": "HP-001", "name": "HeatPro Services", "phone": "(713) 555-0401", "address": "321 Thermal Way, Houston, TX"},
        {"id": "HP-002", "name": "Efficient Energy", "phone": "(281) 555-0502", "address": "654 Pump Lane, Katy, TX"},
    ]
}

SERVICEABLE_ZIPS = {"77001", "77002", "77003", "77004", "77005", "77006", "77007", "77008", "77009", "77010"}

@mcp.tool
def check_territory(zip_code: str = "77001") -> dict:
    """Check if a location is within the serviceable territory."""
    serviceable = zip_code in SERVICEABLE_ZIPS
    return {
        "status": "ok",
        "data": {
            "zip": zip_code,
            "serviceable": serviceable,
            "message": "Within service territory" if serviceable else "Outside service territory - third-party providers available"
        }
    }

@mcp.tool
def get_service_directory(product_type: str = "HEAT", max_results: int = 3) -> dict:
    """Get list of service providers for a product type."""
    providers = PROVIDERS.get(product_type.upper(), PROVIDERS["HEAT"])[:max_results]
    return {"status": "ok", "data": {"product_type": product_type, "providers": providers}}

@mcp.tool
def route_to_queue(queue: str, priority: str = "normal", case_id: str = None, issue_description: str = "") -> dict:
    """Route a case to a service queue."""
    cid = case_id or f"CASE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    return {
        "status": "ok",
        "data": {
            "case_id": cid, 
            "queue": queue, 
            "priority": priority, 
            "issue_description": issue_description,
            "estimated_response": "24-48 hours",
        }
    }

@mcp.tool
def generate_paypal_link(amount: float, description: str = "Warranty Service") -> dict:
    """Generate a PayPal payment link."""
    link_id = uuid.uuid4().hex[:8]
    return {
        "status": "ok",
        "data": {
            "payment_url": f"https://paypal.me/warrantyservice/{link_id}?amount={amount}",
            "amount": amount,
            "description": description,
            "expires_in": "24 hours"
        }
    }

@mcp.tool
def log_decline_reason(reason: str, case_id: str = None) -> dict:
    """Log the reason a customer declined service."""
    log_id = f"LOG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return {"status": "ok", "data": {"log_id": log_id, "reason": reason, "logged_at": datetime.now().isoformat()}}

@mcp.tool
def notify_next_steps(message: str, channel: str = "email") -> dict:
    """Send notification about next steps to customer."""
    return {"status": "ok", "data": {"notification_sent": True, "channel": channel, "message_preview": message[:100]}}

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8003)
