# Actions MCP Server

## Structure

```
actions/
├── main.py           # MCP server entry point (runs on port 8003)
└── src/              # Integration code for MVP
    ├── crm_integration.py    # CRM system integration placeholder
    ├── payment_gateway.py    # Payment processing placeholder
    ├── service_directory.py  # Service provider lookup placeholder
    └── __init__.py           # Module exports
```

## Current (POC) Usage

The server currently uses hardcoded data in `main.py`:
- Service providers (PROVIDERS dict)
- Serviceable zip codes (SERVICEABLE_ZIPS set)
- Mock payment links
- Simple logging

Run the server:
```bash
python src/servers/actions/main.py
```

## Future (MVP) Integration

When moving to MVP, integrate real systems:

### CRM Integration (crm_integration.py)
- Create cases in Salesforce / Dynamics 365
- Update case status and priority
- Track customer service history
- Route to appropriate queues

### Payment Gateway (payment_gateway.py)
- Generate real PayPal payment links
- Create Stripe checkout sessions
- Verify payment completion
- Process refunds

### Service Directory (service_directory.py)
- Query provider database with geospatial search
- Check real-time provider availability
- Retrieve customer reviews and ratings
- Filter by service area and capabilities

### Migration Path
1. Implement CRM client in `src/crm_integration.py`
2. Set up payment gateway credentials and SDK
3. Connect service directory to provider database
4. Update `main.py` tools to call integration modules
5. Add proper error handling and logging
6. Implement retry logic and circuit breakers
