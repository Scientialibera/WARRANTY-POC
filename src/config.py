"""
Configuration Management for Warranty POC
==========================================
Centralized configuration for MCP servers, authentication, and deployment settings.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    
    name: str
    port: int
    url: Optional[str] = None  # If deployed remotely (e.g., Azure Container Apps)
    
    # OAuth 2.1 Authorization Settings
    enable_auth: bool = Field(default=False, description="Enable OAuth 2.1 token validation")
    required_role: Optional[str] = Field(default=None, description="Required Azure AD role for access")
    token_validation_uri: Optional[str] = Field(
        default=None, 
        description="URI to validate tokens (e.g., Microsoft Entra ID validation endpoint)"
    )
    audience: Optional[str] = Field(
        default=None,
        description="Expected audience claim in the token (RFC 8707)"
    )
    
    def get_url(self) -> str:
        """Get the MCP server URL (local or remote)."""
        if self.url:
            return self.url
        return f"http://127.0.0.1:{self.port}/mcp"


class AuthConfig(BaseModel):
    """Azure authentication configuration."""
    
    use_managed_identity: bool = Field(
        default=False,
        description="Use Azure Managed Identity for authentication"
    )
    token_scope: str = Field(
        default="https://cognitiveservices.azure.com/.default",
        description="OAuth scope for token requests"
    )
    entra_tenant_id: Optional[str] = Field(
        default=None,
        description="Microsoft Entra ID tenant ID"
    )


class WarrantyConfig(BaseModel):
    """Main configuration for WARRANTY-POC application."""
    
    # Azure OpenAI Settings
    azure_openai_endpoint: str = Field(
        default="https://aura-ai-foundry-2025.cognitiveservices.azure.com/",
        description="Azure OpenAI endpoint URL"
    )
    azure_openai_deployment: str = Field(
        default="gpt-4.1",
        description="Azure OpenAI deployment name"
    )
    azure_openai_api_version: str = Field(
        default="2025-03-01-preview",
        description="Azure OpenAI API version"
    )
    
    # MCP Authorization (OAuth 2.1)
    mcp_authorization: bool = Field(
        default=False,
        description="Enable OAuth 2.1 authorization for MCP servers (required for Azure deployment)"
    )
    
    # Authentication
    auth: AuthConfig = Field(default_factory=AuthConfig)
    
    # MCP Servers
    warranty_server: MCPServerConfig = Field(
        default_factory=lambda: MCPServerConfig(
            name="warranty",
            port=8002,
            enable_auth=False,
            required_role="Warranty.Read",
            audience="api://warranty-mcp-server"
        )
    )
    
    actions_server: MCPServerConfig = Field(
        default_factory=lambda: MCPServerConfig(
            name="actions",
            port=8003,
            enable_auth=False,
            required_role="Warranty.Actions",
            audience="api://actions-mcp-server"
        )
    )
    
    @classmethod
    def from_env(cls) -> "WarrantyConfig":
        """Load configuration from environment variables."""
        
        # Check if MCP authorization is enabled
        mcp_auth = os.environ.get("MCP_AUTHORIZATION", "false").lower() == "true"
        
        # Auth config
        auth = AuthConfig(
            use_managed_identity=os.environ.get("USE_MANAGED_IDENTITY", "false").lower() == "true",
            token_scope=os.environ.get("AZURE_TOKEN_SCOPE", "https://cognitiveservices.azure.com/.default"),
            entra_tenant_id=os.environ.get("ENTRA_TENANT_ID")
        )
        
        # Warranty server config
        warranty_server = MCPServerConfig(
            name="warranty",
            port=int(os.environ.get("WARRANTY_PORT", "8002")),
            url=os.environ.get("WARRANTY_URL"),  # e.g., https://warranty-mcp.azurecontainerapps.io/mcp
            enable_auth=mcp_auth,
            required_role=os.environ.get("WARRANTY_REQUIRED_ROLE", "Warranty.Read"),
            token_validation_uri=os.environ.get("WARRANTY_TOKEN_VALIDATION_URI"),
            audience=os.environ.get("WARRANTY_AUDIENCE", "api://warranty-mcp-server")
        )
        
        # Actions server config
        actions_server = MCPServerConfig(
            name="actions",
            port=int(os.environ.get("ACTIONS_PORT", "8003")),
            url=os.environ.get("ACTIONS_URL"),  # e.g., https://actions-mcp.azurecontainerapps.io/mcp
            enable_auth=mcp_auth,
            required_role=os.environ.get("ACTIONS_REQUIRED_ROLE", "Warranty.Actions"),
            token_validation_uri=os.environ.get("ACTIONS_TOKEN_VALIDATION_URI"),
            audience=os.environ.get("ACTIONS_AUDIENCE", "api://actions-mcp-server")
        )
        
        return cls(
            azure_openai_endpoint=os.environ.get(
                "AZURE_OPENAI_ENDPOINT", 
                "https://aura-ai-foundry-2025.cognitiveservices.azure.com/"
            ),
            azure_openai_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
            azure_openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview"),
            mcp_authorization=mcp_auth,
            auth=auth,
            warranty_server=warranty_server,
            actions_server=actions_server
        )


# Global config instance
config = WarrantyConfig.from_env()
