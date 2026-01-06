"""
Actions MCP Server

This MCP server provides action execution capabilities for the warranty workflow:
- route_to_queue: Route case to service queue
- get_service_directory: Get list of service providers
- check_territory: Check if location is serviceable
- generate_paypal_link: Generate PayPal payment link
- log_decline_reason: Log customer decline reason
- notify_next_steps: Send notification to customer

For the POC, these are dummy implementations that simulate real actions.
"""

import json
import sys
import uuid
from datetime import datetime
from typing import Any


# Dummy service providers database
SERVICE_PROVIDERS = {
    "SALT": [
        {
            "id": "SP-001",
            "name": "AquaPure Service Co.",
            "address": "123 Water St, Houston, TX 77001",
            "phone": "(713) 555-0101",
            "rating": 4.8,
            "certifications": ["Certified Water Treatment Specialist", "Factory Authorized"],
            "distance_miles": 5.2
        },
        {
            "id": "SP-002",
            "name": "SoftWater Solutions",
            "address": "456 Mineral Ave, Houston, TX 77002",
            "phone": "(713) 555-0202",
            "rating": 4.5,
            "certifications": ["Factory Authorized"],
            "distance_miles": 8.7
        },
        {
            "id": "SP-003",
            "name": "ClearFlow Technicians",
            "address": "789 Filter Blvd, Sugar Land, TX 77478",
            "phone": "(281) 555-0303",
            "rating": 4.9,
            "certifications": ["Master Technician", "Factory Authorized"],
            "distance_miles": 12.3
        }
    ],
    "HEAT": [
        {
            "id": "HP-001",
            "name": "HeatPro Services",
            "address": "321 Thermal Way, Houston, TX 77003",
            "phone": "(713) 555-0401",
            "rating": 4.7,
            "certifications": ["HVAC Certified", "Heat Pump Specialist", "Factory Authorized"],
            "distance_miles": 6.1
        },
        {
            "id": "HP-002",
            "name": "Efficient Energy Solutions",
            "address": "654 Pump Lane, Katy, TX 77449",
            "phone": "(281) 555-0502",
            "rating": 4.6,
            "certifications": ["Energy Star Partner", "Factory Authorized"],
            "distance_miles": 15.4
        },
        {
            "id": "HP-003",
            "name": "WarmWater Experts",
            "address": "987 Heat St, Pearland, TX 77584",
            "phone": "(832) 555-0603",
            "rating": 4.8,
            "certifications": ["Master Heat Pump Technician", "Factory Authorized"],
            "distance_miles": 18.9
        }
    ]
}

# Serviceable territories (dummy data - zip codes that are serviceable)
SERVICEABLE_ZIPS = {
    "77001", "77002", "77003", "77004", "77005", "77006", "77007", "77008",
    "77009", "77010", "77019", "77020", "77021", "77022", "77023", "77024",
    "77025", "77026", "77027", "77028", "77029", "77030", "77031", "77032",
    "77098", "77099"
}

# In-memory stores for the POC
queued_cases = []
logged_declines = []
generated_links = []
sent_notifications = []


def route_to_queue(queue: str, case_context: dict, priority: str = "normal", 
                   idempotency_key: str = None) -> dict:
    """
    Route a case to the specified service queue.
    
    Args:
        queue: Queue name (e.g., "WarrantySalt", "WarrantyHeat")
        case_context: Full case context to attach
        priority: Priority level (low, normal, high, urgent)
        idempotency_key: Optional key to prevent duplicates
    """
    # Check for duplicate using idempotency key
    if idempotency_key:
        for case in queued_cases:
            if case.get("idempotency_key") == idempotency_key:
                return {
                    "status": "ok",
                    "data": {
                        "case_id": case["case_id"],
                        "queue": case["queue"],
                        "message": "Case already queued (duplicate prevented)",
                        "duplicate": True
                    }
                }
    
    case_id = f"CASE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    queue_entry = {
        "case_id": case_id,
        "queue": queue,
        "priority": priority,
        "case_context": case_context,
        "created_at": datetime.now().isoformat(),
        "status": "pending",
        "idempotency_key": idempotency_key
    }
    
    queued_cases.append(queue_entry)
    
    return {
        "status": "ok",
        "data": {
            "case_id": case_id,
            "queue": queue,
            "priority": priority,
            "estimated_response_time": "24-48 hours" if priority == "normal" else "4-8 hours",
            "position_in_queue": len([c for c in queued_cases if c["queue"] == queue])
        }
    }


def get_service_directory(product_type: str, location: dict, 
                          max_distance_miles: float = 50,
                          filters: dict = None) -> dict:
    """
    Get list of service providers for a product type and location.
    
    Args:
        product_type: "SALT" or "HEAT"
        location: Customer location (zip, city, state)
        max_distance_miles: Maximum search radius
        filters: Optional filters (certified_only, available_now)
    """
    providers = SERVICE_PROVIDERS.get(product_type, [])
    
    if not providers:
        return {
            "status": "error",
            "error_code": "NO_PROVIDERS",
            "message": f"No service providers found for product type: {product_type}"
        }
    
    # Filter by distance
    filtered = [p for p in providers if p["distance_miles"] <= max_distance_miles]
    
    # Apply additional filters
    if filters:
        if filters.get("certified_only"):
            filtered = [p for p in filtered if "Factory Authorized" in p["certifications"]]
    
    # Sort by distance
    filtered.sort(key=lambda x: x["distance_miles"])
    
    return {
        "status": "ok",
        "data": {
            "product_type": product_type,
            "location": location,
            "provider_count": len(filtered),
            "providers": filtered
        }
    }


def check_territory(location: dict) -> dict:
    """
    Check if a location is within serviceable territory.
    
    Args:
        location: Location to check (zip, city, state, or lat/lon)
    """
    zip_code = location.get("zip", "")
    
    # Clean up zip code
    if zip_code:
        zip_code = zip_code.strip()[:5]
    
    is_serviceable = zip_code in SERVICEABLE_ZIPS
    
    return {
        "status": "ok",
        "data": {
            "location": location,
            "serviceable": is_serviceable,
            "territory_name": "Houston Metro Area" if is_serviceable else None,
            "nearest_serviceable_zip": "77001" if not is_serviceable else None,
            "message": "Location is within our direct service territory" if is_serviceable 
                       else "Location is outside our direct service territory. Third-party service providers are available."
        }
    }


def generate_paypal_link(amount: float, metadata: dict, currency: str = "USD",
                         idempotency_key: str = None) -> dict:
    """
    Generate a PayPal payment link.
    
    Args:
        amount: Amount in specified currency
        metadata: Case metadata to attach
        currency: Currency code (default USD)
        idempotency_key: Optional key to prevent duplicate links
    """
    # Check for duplicate
    if idempotency_key:
        for link in generated_links:
            if link.get("idempotency_key") == idempotency_key:
                return {
                    "status": "ok",
                    "data": {
                        "payment_id": link["payment_id"],
                        "payment_url": link["payment_url"],
                        "message": "Payment link already generated (duplicate prevented)",
                        "duplicate": True
                    }
                }
    
    payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
    
    # Generate dummy PayPal link (sandbox URL)
    payment_url = f"https://www.sandbox.paypal.com/checkoutnow?token={payment_id}"
    
    link_entry = {
        "payment_id": payment_id,
        "payment_url": payment_url,
        "amount": amount,
        "currency": currency,
        "metadata": metadata,
        "created_at": datetime.now().isoformat(),
        "status": "pending",
        "idempotency_key": idempotency_key
    }
    
    generated_links.append(link_entry)
    
    return {
        "status": "ok",
        "data": {
            "payment_id": payment_id,
            "payment_url": payment_url,
            "amount": amount,
            "currency": currency,
            "expires_in_hours": 72,
            "description": metadata.get("description", "Service charge payment")
        }
    }


def log_decline_reason(reason: str, context: dict, idempotency_key: str = None) -> dict:
    """
    Log the reason for customer declining service.
    
    Args:
        reason: The decline reason provided by customer
        context: Case context at time of decline
        idempotency_key: Optional key to prevent duplicate logs
    """
    # Check for duplicate
    if idempotency_key:
        for log in logged_declines:
            if log.get("idempotency_key") == idempotency_key:
                return {
                    "status": "ok",
                    "data": {
                        "log_id": log["log_id"],
                        "message": "Decline already logged (duplicate prevented)",
                        "duplicate": True
                    }
                }
    
    log_id = f"LOG-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    log_entry = {
        "log_id": log_id,
        "reason": reason,
        "context": context,
        "logged_at": datetime.now().isoformat(),
        "idempotency_key": idempotency_key
    }
    
    logged_declines.append(log_entry)
    
    return {
        "status": "ok",
        "data": {
            "log_id": log_id,
            "reason": reason,
            "logged_at": log_entry["logged_at"],
            "message": "Decline reason logged successfully"
        }
    }


def notify_next_steps(channel: str, template_id: str, context: dict,
                      recipient: dict = None) -> dict:
    """
    Send notification to customer about next steps.
    
    Args:
        channel: Notification channel (email, sms, portal, chat)
        template_id: Template to use
        context: Template context data
        recipient: Recipient information
    """
    notification_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    
    # Template messages (dummy)
    templates = {
        "warranty_queued": "Your warranty claim has been received. A specialist will contact you within {estimated_response_time}. Case ID: {case_id}",
        "service_scheduled": "Your service appointment has been scheduled. A technician will arrive on {scheduled_date}.",
        "payment_received": "Thank you! Your payment of ${amount} has been received. Your service will be scheduled shortly.",
        "decline_acknowledged": "We understand your decision. If you change your mind, please contact us anytime."
    }
    
    template = templates.get(template_id, "Thank you for contacting us. We will be in touch soon.")
    
    # Simple template substitution
    message = template
    for key, value in context.items():
        message = message.replace("{" + key + "}", str(value))
    
    notification_entry = {
        "notification_id": notification_id,
        "channel": channel,
        "template_id": template_id,
        "message": message,
        "context": context,
        "recipient": recipient,
        "sent_at": datetime.now().isoformat(),
        "status": "sent"
    }
    
    sent_notifications.append(notification_entry)
    
    return {
        "status": "ok",
        "data": {
            "notification_id": notification_id,
            "channel": channel,
            "status": "sent",
            "message_preview": message[:100] + "..." if len(message) > 100 else message
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
                    "tools": {}
                },
                "serverInfo": {
                    "name": "warranty-actions",
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
                        "name": "route_to_queue",
                        "description": "Route a warranty case to the appropriate service queue",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "queue": {"type": "string"},
                                "case_context": {"type": "object"},
                                "priority": {"type": "string"},
                                "idempotency_key": {"type": "string"}
                            },
                            "required": ["queue", "case_context"]
                        }
                    },
                    {
                        "name": "get_service_directory",
                        "description": "Get list of service providers for a product type and location",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "product_type": {"type": "string"},
                                "location": {"type": "object"},
                                "max_distance_miles": {"type": "number"},
                                "filters": {"type": "object"}
                            },
                            "required": ["product_type", "location"]
                        }
                    },
                    {
                        "name": "check_territory",
                        "description": "Check if a location is within serviceable territory",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "object"}
                            },
                            "required": ["location"]
                        }
                    },
                    {
                        "name": "generate_paypal_link",
                        "description": "Generate a PayPal payment link for service charges",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "amount": {"type": "number"},
                                "metadata": {"type": "object"},
                                "currency": {"type": "string"},
                                "idempotency_key": {"type": "string"}
                            },
                            "required": ["amount", "metadata"]
                        }
                    },
                    {
                        "name": "log_decline_reason",
                        "description": "Log the reason for customer declining service",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string"},
                                "context": {"type": "object"},
                                "idempotency_key": {"type": "string"}
                            },
                            "required": ["reason", "context"]
                        }
                    },
                    {
                        "name": "notify_next_steps",
                        "description": "Send notification to customer about next steps",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "channel": {"type": "string"},
                                "template_id": {"type": "string"},
                                "context": {"type": "object"},
                                "recipient": {"type": "object"}
                            },
                            "required": ["channel", "template_id", "context"]
                        }
                    }
                ]
            }
        }
    
    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        tool_handlers = {
            "route_to_queue": lambda: route_to_queue(
                queue=arguments.get("queue"),
                case_context=arguments.get("case_context", {}),
                priority=arguments.get("priority", "normal"),
                idempotency_key=arguments.get("idempotency_key")
            ),
            "get_service_directory": lambda: get_service_directory(
                product_type=arguments.get("product_type"),
                location=arguments.get("location", {}),
                max_distance_miles=arguments.get("max_distance_miles", 50),
                filters=arguments.get("filters")
            ),
            "check_territory": lambda: check_territory(
                location=arguments.get("location", {})
            ),
            "generate_paypal_link": lambda: generate_paypal_link(
                amount=arguments.get("amount", 0),
                metadata=arguments.get("metadata", {}),
                currency=arguments.get("currency", "USD"),
                idempotency_key=arguments.get("idempotency_key")
            ),
            "log_decline_reason": lambda: log_decline_reason(
                reason=arguments.get("reason", ""),
                context=arguments.get("context", {}),
                idempotency_key=arguments.get("idempotency_key")
            ),
            "notify_next_steps": lambda: notify_next_steps(
                channel=arguments.get("channel"),
                template_id=arguments.get("template_id"),
                context=arguments.get("context", {}),
                recipient=arguments.get("recipient")
            )
        }
        
        handler = tool_handlers.get(tool_name)
        if handler:
            result = handler()
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
    sys.stderr.write("Actions MCP Server starting...\n")
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
