# Warranty Orchestrator POC

A proof-of-concept warranty service orchestrator using the Microsoft Agent Framework with MCP (Model Context Protocol) support.

## Architecture Overview

This POC implements a constrained-plan orchestrator for warranty service workflows based on the following diagram:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WARRANTY ORCHESTRATOR                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐         ┌──────────────────┐         ┌───────────────┐   │
│  │   Planner    │◄───────►│   Orchestrator   │◄───────►│ Warranty Docs │   │
│  │   MCP        │         │                  │         │     MCP       │   │
│  └──────────────┘         └────────┬─────────┘         └───────────────┘   │
│                                    │                                         │
│                           ┌────────┴─────────┐                              │
│                           │                  │                              │
│                    ┌──────▼──────┐    ┌──────▼──────┐                      │
│                    │   Compute   │    │   Actions   │                      │
│                    │   Tool      │    │    MCP      │                      │
│                    └─────────────┘    └─────────────┘                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

1. **Planner MCP Server** - Generates structured execution plans based on workflow contract
2. **Warranty Docs MCP Server** - Provides warranty record lookup and terms
3. **Compute Tool** - Deterministic calculations (charges, warranty windows, proration)
4. **Actions MCP Server** - Executes actions (queue routing, PayPal links, notifications)
5. **Orchestrator** - Main agent that executes plans and maintains state

## Workflow Contract

The orchestrator follows a strict workflow contract:

### Gates (in order)
1. **Login Gate** - User must be logged in
2. **Registration Gate** - User must have registered products
3. **Info Collection** - Product ID and location must be provided

### Product Branching

#### SALT Products
- **Warranty**: Route to queue → Notify customer
- **Non-Warranty**: Return service provider directory

#### HEAT Products (strict step order)
1. Calculate charges (MUST happen first)
2. Ask user to proceed
3. If **Decline**: Log reason → Acknowledge
4. If **Proceed**: Check territory
5. If **Serviceable**: Generate PayPal link
6. If **Not Serviceable**: Return service directory

### Invariants (MUST NOT violate)
- Warranty determination before Salt/Heat branching
- HEAT: Charges calculated before asking to proceed
- HEAT: Proceed confirmation before territory check
- HEAT: Territory check before PayPal link
- Decline path must log reason

## Project Structure

```
WARRANTY-POC/
├── config/
│   ├── agent.toml              # Main configuration
│   ├── system_prompt.txt       # Orchestrator system prompt
│   └── tools/                  # Tool JSON definitions
│       ├── compute.json
│       ├── planner.json
│       ├── warranty_record.json
│       └── ...
├── src/
│   ├── compute/                # Deterministic compute service
│   │   └── service.py
│   ├── mcp_servers/            # MCP server implementations
│   │   ├── planner.py
│   │   ├── warranty_docs.py
│   │   └── actions.py
│   ├── models/                 # Data models
│   │   └── case_context.py
│   └── orchestrator/           # Main orchestrator
│       └── warranty_orchestrator.py
├── tests/
│   ├── test_compute.py         # Compute tool unit tests
│   ├── test_mcp_servers.py     # MCP integration tests
│   └── test_golden_paths.py    # End-to-end workflow tests
├── main.py                     # CLI entry point
├── pyproject.toml              # Project configuration
└── README.md
```

## Installation

### Prerequisites
- Python 3.10+
- Azure OpenAI resource (optional - works without for rule-based flow)

### Setup

```powershell
# Clone or create the project
cd WARRANTY-POC

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e ".[dev]"
```

### Environment Variables (optional)

```powershell
# For Azure OpenAI integration
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
```

## Running the POC

### Interactive CLI

```powershell
python main.py
```

Commands:
- `/login` - Simulate user login
- `/register <product_id>` - Register a product (e.g., `/register HEAT-001`)
- `/location <zip>` - Set location (e.g., `/location 77001`)
- `/status` - Show current session status
- `/reset` - Reset session
- `/quit` - Exit

### Demo Mode

```powershell
python main.py --demo
```

Runs through several pre-configured scenarios showing different workflow paths.

## Running Tests

```powershell
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_compute.py -v

# Run with coverage
pytest tests/ -v --cov=src
```

## Dummy Data

### Products

| Product ID | Type | Status | Notes |
|------------|------|--------|-------|
| SALT-001 | SALT | Full warranty | All coverage active |
| SALT-002 | SALT | Partial warranty | Only controller active |
| HEAT-001 | HEAT | Full warranty | New product |
| HEAT-002 | HEAT | Partial warranty | Tank only |
| HEAT-003 | HEAT | Full warranty | Active coverage |

### Serviceable Territories
- Houston Metro Area (zip codes 77001-77099 range)

### Service Providers
- 3 SALT providers
- 3 HEAT providers

## API Examples

### Request Format
```json
{
  "user_message": "My water heater isn't working",
  "logged_in": true,
  "has_registered_products": true,
  "product_id": "HEAT-001",
  "location": {"zip": "77001", "state": "TX"},
  "case_id": null
}
```

### Response Format
```json
{
  "case_id": "CASE-20260106-ABC12345",
  "status": "ok",
  "response": "I've retrieved your warranty information...",
  "action": "ASK_USER",
  "action_data": {
    "required_fields": ["proceed_confirmation"]
  }
}
```

## Extending the POC

### Adding New Tools

1. Create tool config: `config/tools/<tool_name>.json`
2. Implement service: `src/<tool_name>/service.py`
3. Add to orchestrator routing in `warranty_orchestrator.py`

### Adding New MCP Servers

1. Create server: `src/mcp_servers/<server_name>.py`
2. Register in `config/agent.toml`:
```toml
[[tool.agent.mcp]]
name = "new_server"
type = "stdio"
enabled = true
command = "python"
args = ["-m", "src.mcp_servers.new_server"]
```

## Integration with Copilot Studio

This orchestrator is designed to be called from Copilot Studio when self-help is insufficient:

1. Copilot Studio handles simple questions via KB
2. For warranty service requests, it calls the orchestrator with user context
3. Orchestrator returns structured responses and actions
4. Copilot Studio renders responses and handles action triggers

## License

MIT
