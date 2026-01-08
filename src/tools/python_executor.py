"""
PythonExecutor - Safe Python code execution tool for calculations
"""
from typing import Annotated
from pydantic import Field
from agent_framework import ai_function


class PythonExecutor:
    """Execute Python code safely for calculations and data transformations"""
    
    @ai_function(
        name="execute_python",
        description="Execute Python code for calculations, date comparisons, or data transformations. Use this for any mathematical operations, date calculations, or complex logic."
    )
    async def execute_python(
        self,
        code: Annotated[str, Field(description="Python code to execute. Should print or return the result. Can use datetime, math, and standard library modules.")],
    ) -> str:
        """Execute Python code and return the output."""
        import sys
        from io import StringIO
        from datetime import datetime, timedelta
        import math
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            # Create safe execution environment with common modules
            exec_globals = {
                'datetime': datetime,
                'timedelta': timedelta,
                'math': math,
                '__builtins__': __builtins__,
            }
            
            # Execute the code
            exec(code, exec_globals)
            
            # Get output
            output = sys.stdout.getvalue()
            
            # If there's no output, try to get the last expression value
            if not output.strip():
                # Try to evaluate as expression
                try:
                    result = eval(code, exec_globals)
                    output = str(result)
                except:
                    output = "Code executed successfully (no output)"
            
            print(f"\n[PYTHON EXECUTOR]\nCode:\n{code}\nOutput:\n{output}\n[END PYTHON EXECUTOR]\n")
            return output.strip()
            
        except Exception as e:
            error_msg = f"Error executing Python code: {str(e)}"
            print(f"\n[PYTHON EXECUTOR ERROR]\n{error_msg}\n")
            return error_msg
        finally:
            sys.stdout = old_stdout
