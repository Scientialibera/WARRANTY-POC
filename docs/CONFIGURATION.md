# Configuration Reference

Quick reference for all WARRANTY-POC configuration options.

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Environment variables (local development) |
| `src/config.py` | Centralized configuration management |
| `pyproject.toml` | Project metadata and dependencies |

## Key Configuration Classes

### `WarrantyConfig`
Main application configuration loaded from environment variables.

```python
from src.config import config

# Access configuration
print(config.mcp_authorization)  # bool
print(config.azure_openai_endpoint)  # str
print(config.warranty_server.get_url())  # str
```

### `MCPServerConfig`
Configuration for individual MCP servers.

```python
# Warranty server config
config.warranty_server.port  # int (8002)
config.warranty_server.url  # Optional[str] (Azure URL)
config.warranty_server.enable_auth  # bool
config.warranty_server.required_role  # str ("Warranty.Read")
config.warranty_server.audience  # str ("api://warranty-mcp-server")
```

### `AuthConfig`
Azure authentication settings.

```python
config.auth.use_managed_identity  # bool
config.auth.token_scope  # str
config.auth.entra_tenant_id  # Optional[str]
```

## Environment Variables

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` | aura-ai-foundry... | Azure OpenAI endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | gpt-4.1 | Model deployment name |
| `AZURE_OPENAI_API_VERSION` | 2025-03-01-preview | API version |

### Authorization

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_AUTHORIZATION` | false | Enable OAuth 2.1 auth |
| `USE_MANAGED_IDENTITY` | false | Use Azure Managed Identity |
| `ENTRA_TENANT_ID` | - | Microsoft Entra ID tenant |
| `AZURE_TOKEN_SCOPE` | cognitiveservices... | Token scope |

### Warranty Server

| Variable | Default | Description |
|----------|---------|-------------|
| `WARRANTY_PORT` | 8002 | Local port |
| `WARRANTY_URL` | - | Azure deployment URL |
| `WARRANTY_AUDIENCE` | api://warranty-mcp-server | OAuth audience |
| `WARRANTY_REQUIRED_ROLE` | Warranty.Read | Required role |
| `WARRANTY_TOKEN_VALIDATION_URI` | - | JWKS endpoint |

### Actions Server

| Variable | Default | Description |
|----------|---------|-------------|
| `ACTIONS_PORT` | 8003 | Local port |
| `ACTIONS_URL` | - | Azure deployment URL |
| `ACTIONS_AUDIENCE` | api://actions-mcp-server | OAuth audience |
| `ACTIONS_REQUIRED_ROLE` | Warranty.Actions | Required role |
| `ACTIONS_TOKEN_VALIDATION_URI` | - | JWKS endpoint |

## Configuration Scenarios

### Scenario 1: Local Development

```bash
# .env
MCP_AUTHORIZATION=false
WARRANTY_PORT=8002
ACTIONS_PORT=8003
```

**Behavior:**
- No authentication required
- Servers run on localhost
- Fast iteration for development
- Agent connects to `http://127.0.0.1:8002/mcp`

### Scenario 2: Hybrid (Local Servers + Azure OpenAI)

```bash
# .env
MCP_AUTHORIZATION=false
WARRANTY_PORT=8002
ACTIONS_PORT=8003
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1
```

**Behavior:**
- Local MCP servers (no auth)
- Azure OpenAI for LLM
- Good for testing with production LLM

### Scenario 3: Full Azure Deployment

```bash
# .env or Azure Container Apps environment
MCP_AUTHORIZATION=true
USE_MANAGED_IDENTITY=true
ENTRA_TENANT_ID=12345678-1234-1234-1234-123456789abc

WARRANTY_URL=https://warranty-mcp.azurecontainerapps.io/mcp
WARRANTY_AUDIENCE=api://warranty-mcp-server
WARRANTY_REQUIRED_ROLE=Warranty.Read

ACTIONS_URL=https://actions-mcp.azurecontainerapps.io/mcp
ACTIONS_AUDIENCE=api://actions-mcp-server
ACTIONS_REQUIRED_ROLE=Warranty.Actions

AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1
```

**Behavior:**
- Full OAuth 2.1 token validation
- MCP servers deployed to Azure Container Apps
- Agent uses Managed Identity for tokens
- Secure production deployment

## Programmatic Configuration

### Loading from Environment

```python
from src.config import WarrantyConfig

# Load from environment variables
config = WarrantyConfig.from_env()

print(f"Auth enabled: {config.mcp_authorization}")
print(f"Warranty URL: {config.warranty_server.get_url()}")
```

### Manual Configuration

```python
from src.config import WarrantyConfig, MCPServerConfig, AuthConfig

config = WarrantyConfig(
    azure_openai_endpoint="https://my-endpoint.openai.azure.com/",
    azure_openai_deployment="gpt-4",
    mcp_authorization=True,
    auth=AuthConfig(
        use_managed_identity=True,
        tenant_id="my-tenant-id"
    ),
    warranty_server=MCPServerConfig(
        name="warranty",
        port=8002,
        url="https://warranty.azurecontainerapps.io/mcp",
        enable_auth=True,
        required_role="Warranty.Read",
        audience="api://warranty-mcp-server"
    )
)
```

## MCP Server Configuration

### Server-Side (main.py)

```python
import os
from src.servers.auth_middleware import OAuth2TokenValidator

# Check if auth is enabled
ENABLE_AUTH = os.environ.get("MCP_AUTHORIZATION", "false").lower() == "true"

if ENABLE_AUTH:
    validator = OAuth2TokenValidator(
        audience=os.environ.get("WARRANTY_AUDIENCE", "api://warranty-mcp-server"),
        required_role=os.environ.get("WARRANTY_REQUIRED_ROLE", "Warranty.Read"),
        tenant_id=os.environ.get("ENTRA_TENANT_ID")
    )
```

### Client-Side (agent)

```python
from src.config import config
from agent_framework import MCPStreamableHTTPTool
from azure.identity import DefaultAzureCredential

if config.mcp_authorization:
    credential = DefaultAzureCredential()
    
    # Get token for warranty server
    warranty_token = credential.get_token(config.warranty_server.audience)
    
    # Create MCP tool with auth header
    warranty_tool = MCPStreamableHTTPTool(
        name="Warranty",
        url=config.warranty_server.get_url(),
        headers={"Authorization": f"Bearer {warranty_token.token}"}
    )
```

## Validation

### Check Current Configuration

```python
from src.config import config

print("="*60)
print("WARRANTY POC CONFIGURATION")
print("="*60)
print(f"MCP Authorization: {config.mcp_authorization}")
print(f"Use Managed Identity: {config.auth.use_managed_identity}")
print(f"Warranty Server: {config.warranty_server.get_url()}")
print(f"  - Auth Enabled: {config.warranty_server.enable_auth}")
print(f"  - Audience: {config.warranty_server.audience}")
print(f"  - Required Role: {config.warranty_server.required_role}")
print(f"Actions Server: {config.actions_server.get_url()}")
print(f"  - Auth Enabled: {config.actions_server.enable_auth}")
print(f"  - Audience: {config.actions_server.audience}")
print(f"  - Required Role: {config.actions_server.required_role}")
print("="*60)
```

## Troubleshooting

### "Authorization required" Error

**Problem:** MCP server returns 401 Unauthorized

**Solutions:**
1. Check `MCP_AUTHORIZATION` is set correctly on both client and server
2. Verify token audience matches server's expected audience
3. Check Managed Identity has proper role assignments
4. Verify `ENTRA_TENANT_ID` is correct

### "Invalid audience" Error

**Problem:** Token validation fails with audience mismatch

**Solutions:**
1. Ensure `WARRANTY_AUDIENCE` matches the app registration
2. Check client is requesting token for correct audience
3. Verify token is sent to correct server (not mixed up)

### "Insufficient permissions" Error

**Problem:** Server returns 403 Forbidden

**Solutions:**
1. Check required role matches app registration
2. Verify Managed Identity has been granted the role
3. Check token `roles` claim contains required role
4. Wait for role assignment propagation (can take 5-10 min)

## Best Practices

1. **Never commit `.env` files** - use `.env.example` as template
2. **Use different audiences** for each server (RFC 8707)
3. **Use Managed Identity** in Azure (don't use service principals)
4. **Enable auth in production** - disable only for local dev
5. **Rotate secrets regularly** - let Azure handle token rotation
6. **Monitor auth failures** - log 401/403 responses for security
