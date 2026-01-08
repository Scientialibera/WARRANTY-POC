import asyncio
from src.agent import create_warranty_agent

async def test():
    agent = create_warranty_agent()
    
    print("\n" + "="*80)
    print("STARTING TEST")
    print("="*80)
    
    result = await agent.run('My water softener serial SN-SALT-2024-001234 needs service. ZIP 77003.')
    
    # Check tool calls
    print('\n' + "="*80)
    print('TOOL CALLS MADE')
    print("="*80)
    if hasattr(result, 'raw_representation') and result.raw_representation:
        raw = result.raw_representation
        if hasattr(raw, 'messages') and raw.messages:
            for message in raw.messages:
                if hasattr(message, 'contents') and message.contents:
                    for content in message.contents:
                        content_type = type(content).__name__
                        if content_type == 'FunctionCallContent':
                            tool_name = getattr(content, 'name', 'unknown')
                            args_str = getattr(content, 'arguments', '{}')
                            print(f'  [{tool_name}]')
                            print(f'    Arguments: {args_str}')
    
    print('\n' + "="*80)
    print('FINAL RESPONSE')
    print("="*80)
    print(result.text)
    print("="*80)

asyncio.run(test())
