# Warranty MCP Server

## Structure

```
warranty/
├── main.py           # MCP server entry point (runs on port 8002)
└── src/              # Integration code for MVP
    ├── database.py       # Database integration placeholder
    ├── api_client.py     # External API client placeholder
    └── __init__.py       # Module exports
```

## Current (POC) Usage

The server currently uses hardcoded data in `main.py`:
- Product database (PRODUCTS dict)
- Warranty terms (WARRANTY_TERMS dict)

Run the server:
```bash
python src/servers/warranty/main.py
```

## Future (MVP) Integration

When moving to MVP, integrate real data sources:

### Database Integration (database.py)
- Connect to SQL Server / CosmosDB / PostgreSQL
- Query products by serial number
- Retrieve warranty terms from database
- Log warranty checks for analytics

### API Integration (api_client.py)
- Call external warranty management APIs
- Handle authentication and rate limiting
- Cache responses for performance
- Validate products against external systems

### Migration Path
1. Implement `WarrantyDatabase` class in `src/database.py`
2. Update `main.py` to use database instead of hardcoded PRODUCTS
3. Add environment variables for connection strings
4. Implement error handling and retry logic
5. Add monitoring and logging
