"""
OAuth 2.1 Token Validation Middleware for MCP Servers
======================================================
Implements OAuth 2.1 Section 5.2 token validation and RFC 8707 audience validation.

Reference:
- OAuth 2.1: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1
- RFC 8707 (Resource Indicators): https://datatracker.ietf.org/doc/html/rfc8707
"""

import os
import jwt
import requests
from typing import Optional, Dict, Any
from functools import wraps
from datetime import datetime, timezone
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse


class OAuth2TokenValidator:
    """
    OAuth 2.1 compliant token validator for MCP servers.
    
    Validates access tokens according to:
    - OAuth 2.1 Section 5.2 (Token Validation)
    - RFC 8707 Section 2 (Audience Validation)
    """
    
    def __init__(
        self,
        audience: str,
        token_validation_uri: Optional[str] = None,
        required_role: Optional[str] = None,
        tenant_id: Optional[str] = None
    ):
        """
        Initialize token validator.
        
        Args:
            audience: Expected audience claim (RFC 8707) - MUST match the intended resource
            token_validation_uri: URI to validate tokens (e.g., Microsoft Entra ID endpoint)
            required_role: Required role claim in the token
            tenant_id: Microsoft Entra ID tenant ID
        """
        self.audience = audience
        self.token_validation_uri = token_validation_uri
        self.required_role = required_role
        self.tenant_id = tenant_id or os.environ.get("ENTRA_TENANT_ID")
        
        # Microsoft Entra ID (Azure AD) JWKS endpoint
        if self.tenant_id and not self.token_validation_uri:
            self.token_validation_uri = (
                f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
            )
        
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_time: Optional[datetime] = None
    
    def _get_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS (JSON Web Key Set) with caching."""
        now = datetime.now(timezone.utc)
        
        # Cache JWKS for 1 hour
        if self._jwks_cache and self._jwks_cache_time:
            age = (now - self._jwks_cache_time).total_seconds()
            if age < 3600:
                return self._jwks_cache
        
        if not self.token_validation_uri:
            raise ValueError("token_validation_uri not configured")
        
        response = requests.get(self.token_validation_uri, timeout=10)
        response.raise_for_status()
        
        self._jwks_cache = response.json()
        self._jwks_cache_time = now
        
        return self._jwks_cache
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate access token according to OAuth 2.1 Section 5.2.
        
        Args:
            token: Bearer access token
            
        Returns:
            dict: Decoded token claims
            
        Raises:
            HTTPException: 401 for invalid/expired tokens, 403 for insufficient permissions
        """
        try:
            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing key ID",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Get JWKS and find matching key
            jwks = self._get_jwks()
            key = None
            
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                    break
            
            if not key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: key not found",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Validate token (OAuth 2.1 Section 5.2)
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self.audience,  # RFC 8707 Section 2: Audience validation
                options={
                    "verify_signature": True,
                    "verify_exp": True,  # Expiration validation
                    "verify_nbf": True,  # Not-before validation
                    "verify_iat": True,  # Issued-at validation
                    "verify_aud": True,  # Audience validation (MUST match)
                }
            )
            
            # Validate required role (authorization check)
            if self.required_role:
                roles = claims.get("roles", [])
                if self.required_role not in roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions: required role '{self.required_role}' not found",
                        headers={"WWW-Authenticate": f'Bearer scope="{self.required_role}"'}
                    )
            
            return claims
            
        except jwt.ExpiredSignatureError:
            # OAuth 2.1 Section 5.3: Expired token
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"Token expired\""}
            )
        
        except jwt.InvalidAudienceError:
            # RFC 8707 Section 2: Audience mismatch
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid audience: expected '{self.audience}'",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"Invalid audience\""}
            )
        
        except jwt.InvalidTokenError as e:
            # OAuth 2.1 Section 5.3: Invalid token
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
            )
        
        except requests.RequestException as e:
            # JWKS fetch error
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to validate token: {str(e)}"
            )


def require_auth(validator: OAuth2TokenValidator):
    """
    FastAPI/FastMCP middleware decorator for OAuth 2.1 token validation.
    
    Usage:
        validator = OAuth2TokenValidator(audience="api://my-service", required_role="MyRole")
        
        @mcp.tool
        @require_auth(validator)
        async def my_tool(request: Request, ...):
            # Token is validated, claims available in request.state.token_claims
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # Check kwargs
                request = kwargs.get("request")
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found - @require_auth must be used with FastAPI routes"
                )
            
            # Extract Authorization header
            auth_header = request.headers.get("Authorization")
            
            if not auth_header:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authorization required",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Parse Bearer token
            scheme, _, token = auth_header.partition(" ")
            
            if scheme.lower() != "bearer":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid authorization scheme: expected 'Bearer'"
                )
            
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing token",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Validate token (OAuth 2.1 Section 5.2)
            claims = validator.validate_token(token)
            
            # Store claims in request state for use in handler
            request.state.token_claims = claims
            
            # Call original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
