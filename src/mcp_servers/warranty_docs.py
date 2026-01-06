"""
Warranty Docs MCP Server

This MCP server provides access to warranty documents and records.
It exposes tools for fetching warranty records and resources for warranty terms.

For the POC, this uses dummy data that simulates a real warranty database.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Any
import uuid


# Dummy warranty database
DUMMY_PRODUCTS = {
    "SALT-001": {
        "product_id": "SALT-001",
        "product_type": "SALT",
        "product_name": "Salt Water Softener Pro",
        "purchase_date": "2024-06-15",
        "warranty_coverage": {
            "parts": {"duration_months": 24, "active": True},
            "labor": {"duration_months": 12, "active": True},
            "controller": {"duration_months": 60, "active": True}
        },
        "serial_number": "SN-SALT-2024-001234"
    },
    "SALT-002": {
        "product_id": "SALT-002",
        "product_type": "SALT",
        "product_name": "Salt Water Softener Basic",
        "purchase_date": "2022-01-10",
        "warranty_coverage": {
            "parts": {"duration_months": 24, "active": False},
            "labor": {"duration_months": 12, "active": False},
            "controller": {"duration_months": 60, "active": True}
        },
        "serial_number": "SN-SALT-2022-005678"
    },
    "HEAT-001": {
        "product_id": "HEAT-001",
        "product_type": "HEAT",
        "product_name": "Heat Pump Water Heater Elite",
        "purchase_date": "2025-01-01",
        "warranty_coverage": {
            "parts": {"duration_months": 36, "active": True},
            "labor": {"duration_months": 12, "active": True},
            "tank": {"duration_months": 120, "active": True}
        },
        "serial_number": "SN-HEAT-2025-001111"
    },
    "HEAT-002": {
        "product_id": "HEAT-002",
        "product_type": "HEAT",
        "product_name": "Heat Pump Water Heater Standard",
        "purchase_date": "2020-06-01",
        "warranty_coverage": {
            "parts": {"duration_months": 36, "active": False},
            "labor": {"duration_months": 12, "active": False},
            "tank": {"duration_months": 120, "active": True}
        },
        "serial_number": "SN-HEAT-2020-002222"
    },
    "HEAT-003": {
        "product_id": "HEAT-003",
        "product_type": "HEAT",
        "product_name": "Heat Pump Water Heater Pro",
        "purchase_date": "2024-03-15",
        "warranty_coverage": {
            "parts": {"duration_months": 36, "active": True},
            "labor": {"duration_months": 12, "active": True},
            "tank": {"duration_months": 120, "active": True}
        },
        "serial_number": "SN-HEAT-2024-003333"
    }
}

# Map serial numbers to product IDs
SERIAL_TO_PRODUCT = {p["serial_number"]: p["product_id"] for p in DUMMY_PRODUCTS.values()}

WARRANTY_TERMS = """
WARRANTY TERMS AND CONDITIONS

1. PARTS WARRANTY
   - Coverage: Defects in materials and workmanship
   - Duration: Varies by product (12-36 months from purchase)
   - Exclusions: Damage from misuse, neglect, or unauthorized modifications

2. LABOR WARRANTY
   - Coverage: Installation and repair labor costs
   - Duration: 12 months from purchase
   - Requirements: Service must be performed by authorized technicians

3. CONTROLLER WARRANTY (SALT Products)
   - Coverage: Electronic controller and sensors
   - Duration: 60 months from purchase
   - Includes: Software updates and calibration

4. TANK WARRANTY (HEAT Products)
   - Coverage: Tank integrity and heating elements
   - Duration: 120 months (10 years) from purchase
   - Pro-rated after first 5 years

5. GENERAL TERMS
   - Proof of purchase required for all warranty claims
   - Warranty is non-transferable
   - Service must be performed by authorized providers
"""


def get_warranty_record(product_id: str = None, serial_number: str = None) -> dict:
    """
    Fetch warranty record for a product.
    
    Args:
        product_id: The product ID to look up
        serial_number: Alternative to product_id - the serial number
        
    Returns:
        Warranty record with product details and coverage status
    """
    # Resolve product ID from serial number if needed
    if not product_id and serial_number:
        product_id = SERIAL_TO_PRODUCT.get(serial_number)
    
    if not product_id:
        return {
            "status": "error",
            "error_code": "MISSING_IDENTIFIER",
            "message": "Either product_id or serial_number is required"
        }
    
    product = DUMMY_PRODUCTS.get(product_id)
    
    if not product:
        return {
            "status": "error",
            "error_code": "PRODUCT_NOT_FOUND",
            "message": f"No warranty record found for product: {product_id}"
        }
    
    # Calculate warranty status
    purchase_date = datetime.strptime(product["purchase_date"], "%Y-%m-%d")
    today = datetime.now()
    
    coverage_status = {}
    active_coverages = []
    
    for coverage_type, coverage_info in product["warranty_coverage"].items():
        expiration_date = purchase_date + timedelta(days=coverage_info["duration_months"] * 30)
        is_active = today < expiration_date
        
        coverage_status[coverage_type] = {
            "active": is_active,
            "duration_months": coverage_info["duration_months"],
            "expiration_date": expiration_date.strftime("%Y-%m-%d"),
            "days_remaining": max(0, (expiration_date - today).days)
        }
        
        if is_active:
            active_coverages.append(coverage_type)
    
    return {
        "status": "ok",
        "data": {
            "product_id": product["product_id"],
            "product_type": product["product_type"],
            "product_name": product["product_name"],
            "serial_number": product["serial_number"],
            "purchase_date": product["purchase_date"],
            "warranty_status": {
                "active": len(active_coverages) > 0,
                "coverage_types": active_coverages,
                "all_coverage": coverage_status
            }
        }
    }


def get_warranty_terms() -> dict:
    """
    Get the warranty terms and conditions document.
    
    Returns:
        Warranty terms text
    """
    return {
        "status": "ok",
        "data": {
            "terms": WARRANTY_TERMS,
            "version": "2024.1",
            "effective_date": "2024-01-01"
        }
    }


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
                    "tools": {},
                    "resources": {}
                },
                "serverInfo": {
                    "name": "warranty-docs",
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
                        "name": "get_warranty_record",
                        "description": "Fetch the warranty record for a product by product_id or serial_number",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "product_id": {
                                    "type": "string",
                                    "description": "The product ID to look up"
                                },
                                "serial_number": {
                                    "type": "string",
                                    "description": "The serial number to look up"
                                }
                            }
                        }
                    },
                    {
                        "name": "get_warranty_terms",
                        "description": "Get the warranty terms and conditions document",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            }
        }
    
    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "resources": [
                    {
                        "uri": "warranty://terms/current",
                        "name": "Current Warranty Terms",
                        "description": "The current warranty terms and conditions",
                        "mimeType": "text/plain"
                    }
                ]
            }
        }
    
    elif method == "resources/read":
        params = request.get("params", {})
        uri = params.get("uri", "")
        
        if uri == "warranty://terms/current":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "text/plain",
                            "text": WARRANTY_TERMS
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": f"Unknown resource: {uri}"
                }
            }
    
    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name == "get_warranty_record":
            result = get_warranty_record(
                product_id=arguments.get("product_id"),
                serial_number=arguments.get("serial_number")
            )
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
        
        elif tool_name == "get_warranty_terms":
            result = get_warranty_terms()
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
    sys.stderr.write("Warranty Docs MCP Server starting...\n")
    sys.stderr.flush()
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                sys.stderr.write(f"JSON parse error: {e}\n")
                sys.stderr.flush()
                continue
            
            response = handle_request(request)
            
            if response is not None:
                response_str = json.dumps(response)
                sys.stdout.write(response_str + "\n")
                sys.stdout.flush()
                
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
