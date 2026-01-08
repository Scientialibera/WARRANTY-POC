# OAuth 2.1 Authorization for MCP Servers

This document describes the OAuth 2.1 authorization implementation for WARRANTY-POC MCP servers, designed for secure Azure deployment.

## Overview

The WARRANTY-POC implements OAuth 2.1 resource server patterns for MCP servers, with full support for:

- **OAuth 2.1** token validation (Section 5.2)
- **RFC 8707** audience validation (Resource Indicators)
- **Microsoft Entra ID** (Azure AD) integration
- **Azure Managed Identity** for client authentication
- **Role-based access control** (RBAC)

## Architecture

```
┌─────────────────┐
│  Warranty Agent │
│  (OAuth Client) │
└────────┬────────┘
         │
         │ 1. Get tokens from Azure Default Credential
         │    - Token for Warranty Server (audience: api://warranty-mcp-server)
         │    - Token for Actions Server (audience: api://actions-mcp-server)
         │
         ├──────────────────────┬──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│ Warranty MCP   │    │  Actions MCP   │    │ Custom Tools   │
│ (Port 8002)    │    │  (Port 8003)   │    │ (No auth)      │
│                │    │                │    │                │
│ 2. Validate    │    │ 2. Validate    │    │ - Planner      │
│    Bearer token│    │    Bearer token│    │ - Python Exec  │
│ 3. Check aud   │    │ 3. Check aud   │    └────────────────┘
│ 4. Check role  │    │ 4. Check role  │
│ 5. Return data │    │ 5. Return data │
└────────────────┘    └────────────────┘
         │                      │
         │ 6. JWKS validation   │
         ▼                      ▼
┌───────────────────────────────────┐
│  Microsoft Entra ID (Azure AD)    │
│  - Issues access tokens           │
│  - Provides JWKS for validation   │
└───────────────────────────────────┘
```

## Configuration

### Environment Variables

#### MCP Authorization Toggle
```bash
# Enable OAuth 2.1 for Azure deployment
MCP_AUTHORIZATION=true

# Disable for local development (no auth)
MCP_AUTHORIZATION=false
```

#### Azure Authentication
```bash
# Use Managed Identity in Azure
USE_MANAGED_IDENTITY=true

# Microsoft Entra ID tenant
ENTRA_TENANT_ID=your-tenant-id-here
```

#### Warranty Server
```bash
# Deployed server URL
WARRANTY_URL=https://warranty-mcp.azurecontainerapps.io/mcp

# OAuth 2.1 audience (RFC 8707)
WARRANTY_AUDIENCE=api://warranty-mcp-server

# Required Azure AD role
WARRANTY_REQUIRED_ROLE=Warranty.Read
```

#### Actions Server
```bash
# Deployed server URL
ACTIONS_URL=https://actions-mcp.azurecontainerapps.io/mcp

# OAuth 2.1 audience (RFC 8707)
ACTIONS_AUDIENCE=api://actions-mcp-server

# Required Azure AD role
ACTIONS_REQUIRED_ROLE=Warranty.Actions
```

## Token Flow

### 1. Client (Agent) - Token Acquisition

When `MCP_AUTHORIZATION=true`, the agent:

```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()

# Get separate tokens for each server (different audiences)
warranty_token = credential.get_token("api://warranty-mcp-server")
actions_token = credential.get_token("api://actions-mcp-server")

# Send tokens via Authorization header
headers = {"Authorization": f"Bearer {warranty_token.token}"}
```

**Critical Requirements:**
- ✅ Client MUST obtain tokens for the correct audience (RFC 8707)
- ✅ Client MUST send tokens only to their intended server
- ❌ Client MUST NOT send tokens to wrong servers
- ❌ Client MUST NOT transit tokens between servers

### 2. Server - Token Validation

MCP servers validate tokens per OAuth 2.1 Section 5.2:

```python
from src.servers.auth_middleware import OAuth2TokenValidator

validator = OAuth2TokenValidator(
    audience="api://warranty-mcp-server",  # MUST match token audience
    required_role="Warranty.Read",
    tenant_id=os.environ.get("ENTRA_TENANT_ID")
)

# Validate token
claims = validator.validate_token(token)
```

**Validation Steps:**
1. Extract Bearer token from `Authorization` header
2. Fetch JWKS from Microsoft Entra ID
3. Verify token signature (RS256)
4. Verify expiration (`exp` claim)
5. Verify not-before (`nbf` claim)
6. **Verify audience** (`aud` claim MUST match server's audience)
7. Verify required role (in `roles` claim)

**Server Requirements:**
- ✅ Server MUST validate tokens were issued for it specifically (audience check)
- ✅ Server MUST reject tokens for other audiences
- ✅ Server MUST only accept tokens from its authorization server
- ❌ Server MUST NOT accept or transit any other tokens

### 3. Error Responses

Per OAuth 2.1 Section 5.3:

| Status | Error | Description | When |
|--------|-------|-------------|------|
| 401 | `invalid_token` | Token invalid/expired | Signature fail, expired, malformed |
| 401 | `invalid_token` | Invalid audience | Audience mismatch (RFC 8707 violation) |
| 403 | `insufficient_scope` | Missing required role | Role not in token claims |
| 400 | `invalid_request` | Malformed authorization | Wrong header format |

Example error response:
```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer error="invalid_token", error_description="Token expired"
Content-Type: application/json

{
    "detail": "Token expired"
}
```

## Deployment Scenarios

### Scenario 1: Local Development (No Auth)

```bash
# .env
MCP_AUTHORIZATION=false
WARRANTY_PORT=8002
ACTIONS_PORT=8003
```

- Servers run locally without authentication
- Agent connects to `http://127.0.0.1:8002/mcp` and `http://127.0.0.1:8003/mcp`
- No tokens required
- Fast iteration during development

### Scenario 2: Azure Container Apps with Managed Identity

```bash
# .env
MCP_AUTHORIZATION=true
USE_MANAGED_IDENTITY=true
ENTRA_TENANT_ID=12345678-1234-1234-1234-123456789abc

# Warranty server
WARRANTY_URL=https://warranty-mcp.azurecontainerapps.io/mcp
WARRANTY_AUDIENCE=api://warranty-mcp-server
WARRANTY_REQUIRED_ROLE=Warranty.Read

# Actions server
ACTIONS_URL=https://actions-mcp.azurecontainerapps.io/mcp
ACTIONS_AUDIENCE=api://actions-mcp-server
ACTIONS_REQUIRED_ROLE=Warranty.Actions
```

**Deployment Steps:**

1. **Register App in Entra ID** (for each MCP server):
   ```
   App Name: warranty-mcp-server
   Audience URI: api://warranty-mcp-server
   Roles: Warranty.Read
   ```

2. **Deploy MCP Servers** to Azure Container Apps:
   ```bash
   az containerapp create \
     --name warranty-mcp \
     --environment warranty-env \
     --image warranty-mcp:latest \
     --env-vars MCP_AUTHORIZATION=true \
                ENTRA_TENANT_ID=$TENANT_ID \
                WARRANTY_AUDIENCE=api://warranty-mcp-server \
                WARRANTY_REQUIRED_ROLE=Warranty.Read
   ```

3. **Assign Managed Identity** to agent app:
   ```bash
   az containerapp identity assign \
     --name warranty-agent \
     --system-assigned
   ```

4. **Grant Role Assignments**:
   ```bash
   # Grant agent's managed identity the Warranty.Read role
   az ad app permission grant \
     --id <agent-app-id> \
     --api <warranty-mcp-app-id> \
     --scope Warranty.Read
   ```

## Security Best Practices

### Token Handling

✅ **DO:**
- Obtain tokens with correct audience for each server
- Send tokens only to their intended audience
- Use HTTPS in production
- Rotate tokens automatically (handled by Azure)
- Cache JWKS to reduce latency

❌ **DON'T:**
- Send warranty server tokens to actions server (or vice versa)
- Transit tokens between services
- Accept tokens without audience validation
- Skip signature verification
- Use HTTP in production

### Server Configuration

✅ **DO:**
- Set unique audience for each server (`api://warranty-mcp-server`, `api://actions-mcp-server`)
- Validate audience on every request
- Require specific roles for fine-grained access
- Return proper OAuth 2.1 error responses
- Log authentication failures for monitoring

❌ **DON'T:**
- Use same audience for multiple servers
- Skip audience validation
- Accept tokens without role checks
- Return generic error messages
- Share JWKS cache between servers

## Testing

### Local Testing (No Auth)
```bash
export MCP_AUTHORIZATION=false
python tests/direct_test.py
```

### Auth Testing (Mock Tokens)
```bash
export MCP_AUTHORIZATION=true
export ENTRA_TENANT_ID=test-tenant
# Use mock token generator for testing
python tests/test_auth.py
```

### Integration Testing (Real Azure)
```bash
# Set real Azure credentials
export MCP_AUTHORIZATION=true
export ENTRA_TENANT_ID=real-tenant-id
export WARRANTY_URL=https://warranty-mcp.azurecontainerapps.io/mcp
# Agent will use DefaultAzureCredential to get real tokens
python tests/direct_test.py
```

## References

- [OAuth 2.1](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1) - Authorization framework
- [RFC 8707](https://datatracker.ietf.org/doc/html/rfc8707) - Resource Indicators (audience validation)
- [Microsoft Entra ID](https://learn.microsoft.com/entra/identity-platform/) - Azure AD documentation
- [Azure Managed Identity](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/) - Token acquisition
