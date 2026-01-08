# MCP Servers

This directory contains the MCP (Model Context Protocol) servers that provide tools for the warranty agent.

## Structure

Each server has its own subdirectory with:
- `main.py` - Server entry point (POC with hardcoded data)
- `src/` - Integration modules for MVP (placeholders)
- `README.md` - Server-specific documentation

## Servers

### Warranty Server (Port 8002)
Provides warranty lookup and product information.

**POC Tools:**
- `get_warranty_terms(serial_number)` - Get product details and warranty coverage

**MVP Integration (src/):**
- `database.py` - Database integration for product/warranty data
- `api_client.py` - External warranty API client

**Run:**
```bash
python -m src.servers.warranty.main
```

### Actions Server (Port 8003)
Provides service actions like territory checks, case routing, payments.

**POC Tools:**
- `check_territory(zip_code)` - Check if ZIP is serviceable
- `get_service_directory(product_type, max_results)` - Get service providers
- `route_to_queue(queue, priority, case_id, issue_description)` - Route to service
- `generate_paypal_link(amount, description)` - Generate payment link
- `log_decline_reason(reason, case_id)` - Log when customer declines

**MVP Integration (src/):**
- `crm_integration.py` - CRM system (Salesforce, Dynamics)
- `payment_gateway.py` - Payment processing (PayPal, Stripe)
- `service_directory.py` - Provider database with geospatial search

**Run:**
```bash
python -m src.servers.actions.main
```

## Migration to MVP

When moving from POC to MVP:

1. **Implement integration modules** in each server's `src/` directory
2. **Update main.py** to call integration modules instead of using hardcoded data
3. **Add environment variables** for connection strings, API keys, etc.
4. **Add error handling** and retry logic
5. **Implement monitoring** and logging for production

See each server's README.md for detailed migration instructions.
