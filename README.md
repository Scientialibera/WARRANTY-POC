# Warranty Service POC

A proof-of-concept warranty service agent using the **Microsoft Agent Framework** with **MCP (Model Context Protocol)** servers and **Azure OpenAI**.

## Features

✨ **Microsoft Agent Framework** - Production-ready agentic orchestration  
🔧 **Custom Tools** - LLM-based planner and Python executor  
🔌 **MCP Servers** - Modular FastMCP HTTP servers for warranty and actions  
🔐 **OAuth 2.1 Authorization** - Secure token validation for Azure deployment  
☁️ **Azure Ready** - Managed Identity, Container Apps, Entra ID integration  
📊 **Comprehensive Testing** - 15 test scenarios with interactive CLI  

## Architecture Overview

This POC implements a fully agentic warranty service workflow using:
- **Microsoft Agent Framework** for the agent loop
- **FastMCP HTTP servers** for tools (warranty lookup, territory checks, routing)
- **Azure OpenAI Responses API** for LLM
- **Code Interpreter** for calculations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WARRANTY AGENT                                     │
│                    (Microsoft Agent Framework)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                         ┌──────────────────┐                                │
│                         │  Azure OpenAI    │                                │
│                         │  (gpt-4.1)       │                                │
│                         └────────┬─────────┘                                │
│                                  │                                          │
│        ┌─────────────────────────┼─────────────────────────┐               │
│        │                         │                         │               │
│  ┌─────▼─────┐            ┌──────▼──────┐           ┌──────▼──────┐       │
│  │  Planner  │            │  Warranty   │           │   Actions   │       │
│  │   MCP     │            │    MCP      │           │    MCP      │       │
│  │ :8001     │            │   :8002     │           │   :8003     │       │
│  └───────────┘            └─────────────┘           └─────────────┘       │
│                                                                              │
│                         ┌──────────────────┐                                │
│                         │ Code Interpreter │                                │
│                         │    (Hosted)      │                                │
│                         └──────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### MCP Servers

| Server | Port | Tools |
|--------|------|-------|
| **Planner** | 8001 | `get_plan` - Generates workflow plans |
| **Warranty** | 8002 | `get_warranty_record`, `get_warranty_terms` - Warranty lookups |
| **Actions** | 8003 | `check_territory`, `get_service_directory`, `route_to_queue`, `generate_paypal_link`, `log_decline_reason` |

### Workflow

1. **User provides product info** (serial number, ZIP code)
2. **Agent calls warranty MCP** to lookup warranty status
3. **Agent calls actions MCP** to check territory serviceability
4. **For HEAT products**: Calculate charges, ask for confirmation, generate payment link
5. **For SALT products**: Route directly to service queue
6. **For expired warranties**: Provide service directory

## Project Structure

```
WARRANTY-POC/
├── src/
│   ├── agent/                  # Main warranty agent
│   │   ├── main.py            # Agent creation and orchestration
│   │   └── __init__.py
│   ├── tools/                  # Custom agent tools
│   │   ├── planner.py         # LLM-based planning tool
│   │   ├── python_executor.py # Python code execution tool
│   │   └── __init__.py
│   ├── prompts/                # Dynamic prompt generation
│   │   ├── agent_system_prompt.py
│   │   ├── planner_prompt.py
│   │   └── __init__.py
│   └── servers/                # MCP servers (FastMCP HTTP)
│       ├── warranty/           # Warranty data server (port 8002)
│       │   ├── main.py        # Server entry point
│       │   ├── src/           # Integration code for MVP
│       │   │   ├── database.py       # DB integration placeholder
│       │   │   ├── api_client.py     # External API placeholder
│       │   │   └── __init__.py
│       │   └── README.md
│       └── actions/            # Actions server (port 8003)
│           ├── main.py        # Server entry point
│           ├── src/           # Integration code for MVP
│           │   ├── crm_integration.py   # CRM placeholder
│           │   ├── payment_gateway.py   # Payment placeholder
│           │   ├── service_directory.py # Provider lookup placeholder
│           │   └── __init__.py
│           └── README.md
├── tests/                      # Test suite
│   ├── direct_test.py         # Interactive CLI testing
│   ├── test_scenarios.py      # Automated scenarios
│   ├── test_cases.txt         # 15 test scenarios
│   └── README.md
├── pyproject.toml              # Project configuration
└── README.md
```

## Installation

```bash
# Clone the repository
git clone https://github.com/Scientialibera/WARRANTY-POC.git
cd WARRANTY-POC

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .
```

## Configuration

### Local Development (No Authentication)

```bash
# Copy example environment file
cp .env.example .env

# Edit .env - ensure MCP_AUTHORIZATION=false for local dev
```

### Azure Deployment (with OAuth 2.1)

For secure Azure deployment with OAuth 2.1 token validation:

```bash
# Set in .env or environment
MCP_AUTHORIZATION=true
ENTRA_TENANT_ID=your-tenant-id
WARRANTY_URL=https://warranty-mcp.azurecontainerapps.io/mcp
ACTIONS_URL=https://actions-mcp.azurecontainerapps.io/mcp
```

See **[docs/OAUTH_AUTHENTICATION.md](docs/OAUTH_AUTHENTICATION.md)** for complete OAuth 2.1 setup guide.

## Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Set your Azure OpenAI endpoint:
   ```dotenv
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT=gpt-4.1
   ```

3. Authenticate with Azure:
   ```bash
   az login
   ```

## Usage

### Run the Agent

```bash
python main.py
```

This will:
1. Start the 3 MCP servers (ports 8001, 8002, 8003)
2. Run test scenarios
3. Display results with tool call tracking

### Run Comprehensive Tests

```bash
python test_scenarios.py
```

This runs 8 test scenarios:
1. **HEAT Full Info** - Active warranty, full workflow
2. **SALT Full Info** - Active warranty, queue routing
3. **Missing Info** - Progressive info gathering
4. **Customer Declines** - Decline logging flow
5. **Expired Warranty** - Service directory provision
6. **Out of Territory** - Third-party provider referral
7. **Code Interpreter** - Cost calculations
8. **Multiple Products** - Multi-product query

### Sample Output

```
============================================================
📈 TEST REPORT SUMMARY
============================================================

    Total Scenarios:    8
    ✅ Passed:          8
    ❌ Failed:          0

    🔧 MCP Tool Calls:         23
    🧮 Code Interpreter Calls: 1

    ⏱️  Total Duration:  68495ms
```

## Available Products (Demo Data)

| Product ID | Serial Number | Type | Warranty Status |
|------------|--------------|------|-----------------|
| SALT-001 | SN-SALT-2024-001234 | SALT | Active |
| SALT-002 | SN-SALT-2022-005678 | SALT | Expired |
| HEAT-001 | SN-HEAT-2025-001111 | HEAT | Active |
| HEAT-002 | SN-HEAT-2020-002222 | HEAT | Expired |

## Serviceable ZIP Codes

77001, 77002, 77003, 77004, 77005, 77006, 77007, 77008, 77009, 77010

## Dependencies

- **agent-framework** >= 1.0.0b251223 - Microsoft Agent Framework
- **fastmcp** >= 2.14.2 - FastMCP for HTTP MCP servers
- **openai** >= 1.50.0 - OpenAI Python SDK
- **azure-identity** - Azure authentication

## License

MIT
