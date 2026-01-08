# Warranty POC - Prompts

This directory contains all the prompts used by the warranty agent system. You can easily edit these files to modify the agent's behavior without changing the code.

## Files

### `agent_system_prompt.txt`
The main system prompt for the warranty orchestrator agent. This prompt:
- Defines the agent's role and responsibilities
- Lists available tools and when to use them
- Provides instructions for handling SALT vs HEAT products
- Specifies when to call the planner (only once at the start)
- Sets expectations for conversation flow

**Edit this to:**
- Change the agent's personality or tone
- Modify the workflow rules
- Add or remove tool descriptions
- Update the current date

### `planner_prompt.txt`
The prompt for the planning sub-agent. This prompt:
- Describes available tools and their parameters
- Defines the standard workflows for SALT and HEAT products
- Specifies what information is needed from users
- Guides the planner on how to structure plans

**Edit this to:**
- Change the planning strategy
- Add new workflow patterns
- Modify tool usage guidance
- Update expected information from users

## Template Variables

### planner_prompt.txt
Uses Python string formatting with these variables:
- `{user_message}` - The user's initial message
- `{context}` - Current conversation context (JSON string)

## Testing Changes

After editing prompts:
1. Save the file
2. Restart any running agents (they load prompts at startup)
3. Test with `python tests/direct_test.py` or `streamlit run app.py`

## Tips

- Keep prompts focused and specific
- Use clear examples when describing complex workflows
- Test changes with multiple test cases
- Version control your prompt changes
