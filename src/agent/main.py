"""
Warranty Agent - Microsoft Agent Framework Pattern

Simple agentic loop using ChatAgent with MCPStreamableHTTPTool for local MCP servers.
Python executor is a custom tool. All others come from MCP URLs.
"""
import os
import asyncio
from typing import Optional, Dict
from openai import AsyncAzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from agent_framework import ChatAgent, MCPStreamableHTTPTool
from agent_framework.openai import OpenAIResponsesClient
from ..tools import PlannerAgent, PythonExecutor
from ..prompts import get_agent_system_prompt
from ..config import config


def create_warranty_agent() -> ChatAgent:
    """Create a warranty agent with MCP tools, PlannerTool, and Python executor."""
    # Create Azure OpenAI client with managed identity
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        config.auth.token_scope
    )
    azure_client = AsyncAzureOpenAI(
        azure_endpoint=config.azure_openai_endpoint,
        azure_deployment=config.azure_openai_deployment,
        api_version=config.azure_openai_api_version,
        azure_ad_token_provider=token_provider,
    )

    # Create planner agent instance
    planner = PlannerAgent(azure_client, config.azure_openai_deployment)
    
    # Create Python executor instance
    python_executor = PythonExecutor()
    
    # Prepare MCP tool headers (OAuth 2.1 Bearer tokens if auth enabled)
    mcp_headers: Optional[Dict[str, str]] = None
    
    if config.mcp_authorization:
        print("[AUTH] MCP Authorization enabled - obtaining access tokens...")
        
        # Get Azure Default Credential
        credential = DefaultAzureCredential()
        
        # Get token for warranty server (with its specific audience)
        warranty_token = credential.get_token(config.warranty_server.audience)
        
        # Get token for actions server (with its specific audience)
        actions_token = credential.get_token(config.actions_server.audience)
        
        print(f"[AUTH] ✓ Obtained token for warranty server (audience: {config.warranty_server.audience})")
        print(f"[AUTH] ✓ Obtained token for actions server (audience: {config.actions_server.audience})")
        
        # Note: Each MCP server will get its own token via headers
        # We'll create separate MCPStreamableHTTPTool instances with different headers
        warranty_headers = {"Authorization": f"Bearer {warranty_token.token}"}
        actions_headers = {"Authorization": f"Bearer {actions_token.token}"}
    else:
        print("[AUTH] MCP Authorization disabled (local development)")
        warranty_headers = None
        actions_headers = None

    # Create agent with PlannerTool (LLM agent), Python executor, and MCP tools
    agent = OpenAIResponsesClient(
        async_client=azure_client,
        model_id=config.azure_openai_deployment,
    ).create_agent(
        name="WarrantyAgent",
        instructions=get_agent_system_prompt(),
        tools=[
            planner.get_plan,  # Function tool that triggers LLM planning agent
            python_executor.execute_python,  # Python code executor
            MCPStreamableHTTPTool(
                name="Warranty", 
                url=config.warranty_server.get_url(),
                headers=warranty_headers
            ),
            MCPStreamableHTTPTool(
                name="Actions", 
                url=config.actions_server.get_url(),
                headers=actions_headers
            ),
        ],
        temperature=0.2,
    )
    return agent


async def run_conversation(agent: ChatAgent, messages: list[str], verbose: bool = True):
    """Run a multi-turn conversation with the agent."""
    responses = []
    for user_message in messages:
        if verbose:
            print(f"\n>>> User: {user_message}")
        result = await agent.run(user_message)
        responses.append(result.text)
        if verbose:
            print(f"<<< Agent: {result.text}")
    return responses


# Simple usage example
if __name__ == "__main__":
    async def main():
        agent = await create_warranty_agent()
        await run_conversation(agent, [
            "My heat pump water heater is making strange noises",
            "Yes, I'd like to proceed with the service"
        ])
    
    asyncio.run(main())
