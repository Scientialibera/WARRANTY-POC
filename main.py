"""
Warranty POC - Main Entry Point

This module provides the main entry point for running the warranty
orchestrator as a CLI application for testing.
"""

import asyncio
import json
import structlog
from typing import Optional

from src.orchestrator import WarrantyOrchestrator


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class WarrantyCLI:
    """Interactive CLI for testing the warranty orchestrator."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.orchestrator = WarrantyOrchestrator()
        self.current_case_id: Optional[str] = None
        
        # Simulated session state (would come from Copilot Studio)
        self.session_state = {
            "logged_in": False,
            "has_registered_products": False,
            "product_id": None,
            "location": {},
            "customer_id": None,
            "customer_name": None
        }
    
    def print_header(self):
        """Print the CLI header."""
        print("\n" + "=" * 60)
        print("  WARRANTY SERVICE POC - Interactive Test CLI")
        print("=" * 60)
        print("\nCommands:")
        print("  /login          - Simulate user login")
        print("  /register <id>  - Register a product (e.g., /register HEAT-001)")
        print("  /location <zip> - Set location (e.g., /location 77001)")
        print("  /status         - Show current session status")
        print("  /reset          - Reset session")
        print("  /help           - Show this help")
        print("  /quit           - Exit")
        print("\nOr just type your message to interact with the warranty bot.")
        print("-" * 60 + "\n")
    
    def print_status(self):
        """Print current session status."""
        print("\n--- Session Status ---")
        print(f"  Logged in: {self.session_state['logged_in']}")
        print(f"  Has registered products: {self.session_state['has_registered_products']}")
        print(f"  Product ID: {self.session_state.get('product_id', 'None')}")
        print(f"  Location: {self.session_state.get('location', {})}")
        print(f"  Current case ID: {self.current_case_id or 'None'}")
        print("----------------------\n")
    
    def handle_command(self, command: str) -> bool:
        """
        Handle a CLI command.
        
        Returns True if command was handled, False otherwise.
        """
        parts = command.strip().split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd == "/login":
            self.session_state["logged_in"] = True
            self.session_state["customer_id"] = "CUST-001"
            self.session_state["customer_name"] = "Test User"
            print("✓ Logged in as Test User (CUST-001)")
            return True
        
        elif cmd == "/register":
            if not self.session_state["logged_in"]:
                print("✗ Please login first (/login)")
                return True
            
            product_id = args[0] if args else "HEAT-001"
            self.session_state["has_registered_products"] = True
            self.session_state["product_id"] = product_id
            print(f"✓ Registered product: {product_id}")
            return True
        
        elif cmd == "/location":
            zip_code = args[0] if args else "77001"
            self.session_state["location"] = {"zip": zip_code}
            print(f"✓ Location set to: {zip_code}")
            return True
        
        elif cmd == "/status":
            self.print_status()
            return True
        
        elif cmd == "/reset":
            self.session_state = {
                "logged_in": False,
                "has_registered_products": False,
                "product_id": None,
                "location": {},
                "customer_id": None,
                "customer_name": None
            }
            self.current_case_id = None
            print("✓ Session reset")
            return True
        
        elif cmd == "/help":
            self.print_header()
            return True
        
        elif cmd == "/quit" or cmd == "/exit":
            print("\nGoodbye!")
            return "exit"
        
        return False
    
    async def process_message(self, message: str):
        """Process a user message through the orchestrator."""
        # Build request
        request = {
            "user_message": message,
            "logged_in": self.session_state["logged_in"],
            "has_registered_products": self.session_state["has_registered_products"],
            "product_id": self.session_state.get("product_id"),
            "location": self.session_state.get("location", {}),
            "customer_id": self.session_state.get("customer_id"),
            "customer_name": self.session_state.get("customer_name"),
            "case_id": self.current_case_id,
            "channel": "chat"
        }
        
        # Process through orchestrator
        result = await self.orchestrator.process_request(request)
        
        # Update case ID
        self.current_case_id = result.get("case_id")
        
        # Display response
        print("\n" + "-" * 40)
        print("BOT:", result.get("response", "No response"))
        
        if result.get("action"):
            print(f"\n[Action: {result['action']}]")
            if result.get("action_data"):
                print(f"[Data: {json.dumps(result['action_data'], indent=2)}]")
        
        print("-" * 40 + "\n")
    
    async def run(self):
        """Run the interactive CLI loop."""
        self.print_header()
        
        while True:
            try:
                user_input = input("YOU: ").strip()
                
                if not user_input:
                    continue
                
                # Check for commands
                if user_input.startswith("/"):
                    result = self.handle_command(user_input)
                    if result == "exit":
                        break
                    elif result:
                        continue
                
                # Process as message
                await self.process_message(user_input)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except EOFError:
                break


async def main():
    """Main entry point."""
    cli = WarrantyCLI()
    await cli.run()


def run_demo():
    """Run a demo scenario showing the workflow."""
    print("\n" + "=" * 60)
    print("  WARRANTY SERVICE POC - Demo Scenario")
    print("=" * 60)
    print("\nThis demo shows a complete HEAT warranty workflow.")
    print("-" * 60)
    
    async def demo():
        orchestrator = WarrantyOrchestrator()
        
        scenarios = [
            # Scenario 1: Not logged in
            {
                "description": "User not logged in",
                "request": {
                    "user_message": "I need help with my water heater",
                    "logged_in": False
                }
            },
            # Scenario 2: Logged in, no products
            {
                "description": "Logged in, no registered products",
                "request": {
                    "user_message": "I need help with my water heater",
                    "logged_in": True,
                    "has_registered_products": False
                }
            },
            # Scenario 3: Full context, HEAT warranty
            {
                "description": "HEAT product with warranty - full flow",
                "request": {
                    "user_message": "My heat pump water heater isn't working",
                    "logged_in": True,
                    "has_registered_products": True,
                    "product_id": "HEAT-001",
                    "location": {"zip": "77001", "state": "TX"}
                }
            },
            # Scenario 4: SALT non-warranty
            {
                "description": "SALT product without warranty",
                "request": {
                    "user_message": "My water softener needs repair",
                    "logged_in": True,
                    "has_registered_products": True,
                    "product_id": "SALT-002",
                    "location": {"zip": "77001", "state": "TX"}
                }
            }
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n{'=' * 50}")
            print(f"Scenario {i}: {scenario['description']}")
            print("=" * 50)
            print(f"\nRequest: {json.dumps(scenario['request'], indent=2)}")
            
            result = await orchestrator.process_request(scenario['request'])
            
            print(f"\nResponse:")
            print(f"  Status: {result.get('status')}")
            print(f"  Case ID: {result.get('case_id')}")
            print(f"  Action: {result.get('action', 'None')}")
            print(f"  Message: {result.get('response', 'No response')[:200]}...")
            
            print("-" * 50)
    
    asyncio.run(demo())


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        asyncio.run(main())
