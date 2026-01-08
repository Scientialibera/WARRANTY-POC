"""Warranty Docs MCP Server - FastMCP HTTP"""
from fastmcp import FastMCP
from datetime import datetime, timedelta
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.servers.auth_middleware import OAuth2TokenValidator, require_auth

mcp = FastMCP("warranty-docs")

# Check if authentication is enabled
ENABLE_AUTH = os.environ.get("MCP_AUTHORIZATION", "false").lower() == "true"
AUTH_VALIDATOR = None

if ENABLE_AUTH:
    AUTH_VALIDATOR = OAuth2TokenValidator(
        audience=os.environ.get("WARRANTY_AUDIENCE", "api://warranty-mcp-server"),
        token_validation_uri=os.environ.get("WARRANTY_TOKEN_VALIDATION_URI"),
        required_role=os.environ.get("WARRANTY_REQUIRED_ROLE", "Warranty.Read"),
        tenant_id=os.environ.get("ENTRA_TENANT_ID")
    )
    print(f"[AUTH] OAuth 2.1 authentication ENABLED for warranty server")
    print(f"[AUTH] Required audience: {AUTH_VALIDATOR.audience}")
    print(f"[AUTH] Required role: {AUTH_VALIDATOR.required_role}")
else:
    print("[AUTH] Authentication DISABLED (local development mode)")

# Product database with warranty info
PRODUCTS = {
    "SN-SALT-2024-001234": {
        "product_id": "SALT-001",
        "serial_number": "SN-SALT-2024-001234",
        "product_type": "SALT",
        "product_name": "Salt Water Softener Pro",
        "purchase_date": "2024-06-15"
    },
    "SN-SALT-2022-005678": {
        "product_id": "SALT-002", 
        "serial_number": "SN-SALT-2022-005678",
        "product_type": "SALT",
        "product_name": "Salt Water Softener Basic",
        "purchase_date": "2022-01-10"
    },
    "SN-HEAT-2025-001111": {
        "product_id": "HEAT-001",
        "serial_number": "SN-HEAT-2025-001111",
        "product_type": "HEAT",
        "product_name": "Heat Pump Water Heater Elite",
        "purchase_date": "2025-01-01"
    },
    "SN-HEAT-2020-002222": {
        "product_id": "HEAT-002",
        "serial_number": "SN-HEAT-2020-002222",
        "product_type": "HEAT",
        "product_name": "Heat Pump Water Heater Standard",
        "purchase_date": "2020-06-01"
    }
}

# Warranty coverage terms by product type
WARRANTY_TERMS = {
    "SALT": {
        "parts_months": 24,
        "labor_months": 12
    },
    "HEAT": {
        "parts_months": "N/A",
        "labor_months": "N/A",
        "tank_months": "N/A"
    }
}

@mcp.tool
def get_warranty_terms(serial_number: str) -> dict:
    """Get complete warranty information including product details and coverage terms for a serial number.
    
    Returns product info (name, type, purchase date, warranty expiry) AND coverage terms (parts/labor/tank months).
    
    Note: If MCP_AUTHORIZATION=true, this endpoint requires OAuth 2.1 Bearer token with Warranty.Read role.
    """
    # Note: Authentication is handled by FastMCP middleware when enabled
    # Token claims would be available in request.state.token_claims if auth is enabled
    
    if serial_number not in PRODUCTS:
        return {
            "status": "error",
            "message": f"Product with serial number {serial_number} not found."
        }
    
    product = PRODUCTS[serial_number]
    product_type = product["product_type"]
    terms = WARRANTY_TERMS[product_type]
    
    # Calculate warranty expiry (use the longest coverage period)
    purchase_date = datetime.strptime(product["purchase_date"], "%Y-%m-%d")
    if product_type == "HEAT":
        warranty_months = terms["tank_months"]  # 120 months for tank
    else:
        warranty_months = terms["parts_months"]  # 24 months for SALT
    
    warranty_expiry = purchase_date + timedelta(days=warranty_months * 30)
    warranty_active = datetime.now() < warranty_expiry
    
    result = {
        "status": "ok",
        "data": {
            # Product details
            "product_id": product["product_id"],
            "serial_number": product["serial_number"],
            "product_type": product["product_type"],
            "product_name": product["product_name"],
            "purchase_date": product["purchase_date"],
            "warranty_expiry": warranty_expiry.strftime("%Y-%m-%d"),
            "warranty_active": warranty_active,
            
            # Coverage terms
            "parts_coverage_months": terms["parts_months"],
            "labor_coverage_months": terms["labor_months"],
        }
    }
    
    # Add tank coverage for HEAT products
    if "tank_months" in terms:
        result["data"]["tank_coverage_months"] = terms["tank_months"]
        description = f"{product['product_name']} warranty covers parts for {terms['parts_months']} months, labor for {terms['labor_months']} months, and tank for {terms['tank_months']} months from purchase date."
    else:
        description = f"{product['product_name']} warranty covers parts for {terms['parts_months']} months and labor for {terms['labor_months']} months from purchase date."
    
    result["data"]["description"] = description
    
    return result

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8002)
