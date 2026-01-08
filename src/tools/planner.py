"""
PlannerAgent - LLM-based planning tool for warranty workflows
"""
from typing import Annotated
from pydantic import Field
from openai import AsyncAzureOpenAI
from agent_framework import ai_function
from ..prompts import get_planner_prompt


class PlannerAgent:
    """Stateful planner agent that uses LLM to generate workflow plans"""
    
    def __init__(self, azure_client: AsyncAzureOpenAI, deployment: str):
        self.azure_client = azure_client
        self.deployment = deployment

    @ai_function(
        name="get_plan",
        description="CALL THIS ONLY ONCE AT THE START OF A NEW CONVERSATION. Generates a workflow plan by invoking a dedicated LLM planning agent. DO NOT call this function again after the first turn - the plan persists for the entire conversation."
    )
    async def get_plan(
        self,
        context: Annotated[str, Field(description="Current conversation context as JSON string including product info, warranty status, location, etc.")],
        user_message: Annotated[str, Field(description="The current user message to plan for")],
    ) -> str:
        """Call the LLM planning agent to generate a plan. SHOULD ONLY BE CALLED ONCE PER CONVERSATION."""
        planning_prompt = get_planner_prompt(user_message, context)

        try:
            response = await self.azure_client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are a planning agent for warranty workflows. Provide clear, actionable plans in markdown format."},
                    {"role": "user", "content": planning_prompt}
                ],
                temperature=0.0,
            )
            
            plan_text = response.choices[0].message.content.strip()
            print(f"\n[PLANNER OUTPUT]\n{plan_text}\n[END PLANNER OUTPUT]\n")
            return plan_text
        except Exception as e:
            error_msg = f"PLANNER FAILED: {str(e)}"
            print(f"\n[PLANNER ERROR] {error_msg}\n")
            raise RuntimeError(error_msg) from e
