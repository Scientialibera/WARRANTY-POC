"""
Warranty POC - Main Entry Point

This module provides the main entry point for running the warranty
orchestrator POC. It auto-populates dummy data to test the blue box
workflow (Orchestrator → Planner → Warranty Details MCP → Compute → Actions MCP).
"""

import asyncio
import json
import sys
import logging
from typing import Optional

from src.orchestrator import WarrantyOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


# =============================================================================
# DUMMY TEST DATA - Pre-populated for POC testing
# =============================================================================

DUMMY_CUSTOMERS = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "customer_name": "John Smith",
        "email": "john.smith@example.com",
        "phone": "555-123-4567"
    },
    "CUST-002": {
        "customer_id": "CUST-002", 
        "customer_name": "Jane Doe",
        "email": "jane.doe@example.com",
        "phone": "555-987-6543"
    }
}

DUMMY_PRODUCTS = {
    "HEAT-001": {
        "product_id": "HEAT-001",
        "product_type": "HEAT",
        "product_name": "ProLine XE Heat Pump Water Heater",
        "serial_number": "HPWH-2024-001234",
        "purchase_date": "2024-06-15",
        "warranty_active": True,
        "coverage_types": ["parts", "labor", "controller"]
    },
    "HEAT-002": {
        "product_id": "HEAT-002",
        "product_type": "HEAT",
        "product_name": "Voltex Hybrid Electric Heat Pump",
        "serial_number": "HPWH-2023-005678",
        "purchase_date": "2023-01-10",
        "warranty_active": False,  # Warranty expired
        "coverage_types": []
    },
    "SALT-001": {
        "product_id": "SALT-001",
        "product_type": "SALT",
        "product_name": "Water Softener Pro 5600",
        "serial_number": "WS-2024-001234",
        "purchase_date": "2024-08-20",
        "warranty_active": True,
        "coverage_types": ["parts", "labor"]
    },
    "SALT-002": {
        "product_id": "SALT-002",
        "product_type": "SALT",
        "product_name": "EcoWater Systems Refiner",
        "serial_number": "WS-2022-009876",
        "purchase_date": "2022-03-15",
        "warranty_active": False,  # Warranty expired
        "coverage_types": []
    }
}

DUMMY_LOCATIONS = {
    "serviceable": {
        "zip": "77001",
        "city": "Houston",
        "state": "TX",
        "country": "US"
    },
    "non_serviceable": {
        "zip": "99501",
        "city": "Anchorage",
        "state": "AK",
        "country": "US"
    }
}


# =============================================================================
# POC TEST SCENARIOS
# =============================================================================

TEST_SCENARIOS = [
    {
        "name": "HEAT + Warranty + Customer Agrees to Charges",
        "description": "Heat pump water heater with active warranty. Some parts not covered, customer agrees to pay charges.",
        "customer": "CUST-001",
        "product": "HEAT-001",
        "location": "serviceable",
        "user_messages": [
            "My heat pump water heater is making strange noises and not heating properly",
            "Yes, I'd like to proceed with the service",
        ],
        "expected_flow": [
            "Get warranty record",
            "Calculate charges for non-covered items",
            "Ask customer if they agree to charges",
            "Check territory serviceability",
            "Generate PayPal link",
            "Complete case"
        ]
    },
    {
        "name": "HEAT + Warranty + Customer Declines",
        "description": "Heat pump with warranty, but customer declines to pay for non-covered parts.",
        "customer": "CUST-001",
        "product": "HEAT-001",
        "location": "serviceable",
        "user_messages": [
            "My water heater controller is broken",
            "No, that's too expensive for me",
        ],
        "expected_flow": [
            "Get warranty record",
            "Calculate charges",
            "Ask customer if they agree",
            "Log decline reason",
            "Complete case"
        ]
    },
    {
        "name": "HEAT + Warranty + Not Serviceable Territory",
        "description": "Heat pump with warranty in a non-serviceable location.",
        "customer": "CUST-001",
        "product": "HEAT-001",
        "location": "non_serviceable",
        "user_messages": [
            "My heat pump water heater stopped working",
            "Yes, I'm willing to pay for service",
        ],
        "expected_flow": [
            "Get warranty record",
            "Calculate charges",
            "Check territory",
            "Return service provider list (not serviceable)",
            "Complete case"
        ]
    },
    {
        "name": "SALT + Warranty",
        "description": "Water softener with active warranty - routes to queue.",
        "customer": "CUST-002",
        "product": "SALT-001",
        "location": "serviceable",
        "user_messages": [
            "My water softener isn't regenerating properly",
        ],
        "expected_flow": [
            "Get warranty record",
            "Route to SALT warranty queue",
            "Complete case"
        ]
    },
    {
        "name": "SALT + No Warranty",
        "description": "Water softener with expired warranty - returns service provider list.",
        "customer": "CUST-002",
        "product": "SALT-002",
        "location": "serviceable",
        "user_messages": [
            "My old water softener is leaking",
        ],
        "expected_flow": [
            "Get warranty record",
            "Return service provider list",
            "Complete case"
        ]
    },
    {
        "name": "HEAT + No Warranty",
        "description": "Heat pump with expired warranty - calculates full charges.",
        "customer": "CUST-001",
        "product": "HEAT-002",
        "location": "serviceable",
        "user_messages": [
            "My heat pump water heater from 2023 needs repair",
            "Yes, I understand I'll pay the full amount",
        ],
        "expected_flow": [
            "Get warranty record",
            "Calculate full charges (no coverage)",
            "Ask customer to agree",
            "Check territory",
            "Generate PayPal link",
            "Complete case"
        ]
    }
]


class POCRunner:
    """Runs the POC test scenarios."""
    
    def __init__(self):
        """Initialize the POC runner with orchestrator."""
        self.orchestrator = WarrantyOrchestrator()
    
    def build_request(
        self,
        user_message: str,
        customer_id: str,
        product_id: str,
        location_key: str,
        case_id: Optional[str] = None
    ) -> dict:
        """Build a request with dummy data pre-populated."""
        customer = DUMMY_CUSTOMERS[customer_id]
        product = DUMMY_PRODUCTS[product_id]
        location = DUMMY_LOCATIONS[location_key]
        
        return {
            "user_message": user_message,
            # Pre-populated - bypassing login/registration gates
            "logged_in": True,
            "has_registered_products": True,
            # Customer info
            "customer_id": customer["customer_id"],
            "customer_name": customer["customer_name"],
            # Product info
            "product_id": product["product_id"],
            "product_type": product["product_type"],
            "product_name": product["product_name"],
            "serial_number": product["serial_number"],
            # Location
            "location": location,
            # Channel
            "channel": "chat",
            # Case continuation
            "case_id": case_id
        }
    
    async def run_scenario(self, scenario: dict) -> dict:
        """Run a single test scenario."""
        print(f"\n{'='*70}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"{'='*70}")
        print(f"Description: {scenario['description']}")
        print(f"Customer: {scenario['customer']}")
        print(f"Product: {scenario['product']} ({DUMMY_PRODUCTS[scenario['product']]['product_type']})")
        print(f"Location: {scenario['location']}")
        print(f"\nExpected Flow:")
        for i, step in enumerate(scenario['expected_flow'], 1):
            print(f"  {i}. {step}")
        print("-" * 70)
        
        case_id = None
        results = []
        
        for i, message in enumerate(scenario['user_messages'], 1):
            print(f"\n>>> Turn {i}: User says: \"{message}\"")
            
            request = self.build_request(
                user_message=message,
                customer_id=scenario['customer'],
                product_id=scenario['product'],
                location_key=scenario['location'],
                case_id=case_id
            )
            
            result = await self.orchestrator.process_request(request)
            case_id = result.get("case_id")
            results.append(result)
            
            print(f"\n<<< Bot Response:")
            print(f"    Status: {result.get('status')}")
            print(f"    Case ID: {case_id}")
            
            response = result.get('response', 'No response')
            # Wrap long responses
            wrapped = '\n    '.join([response[i:i+70] for i in range(0, len(response), 70)])
            print(f"    Message: {wrapped}")
            
            if result.get('action'):
                print(f"    Action: {result['action']}")
                if result.get('action_data'):
                    print(f"    Action Data: {json.dumps(result['action_data'], indent=6)}")
        
        print(f"\n{'='*70}")
        print("SCENARIO COMPLETE")
        print(f"{'='*70}\n")
        
        return {
            "scenario": scenario['name'],
            "case_id": case_id,
            "turns": len(scenario['user_messages']),
            "final_status": results[-1].get('status') if results else None,
            "final_action": results[-1].get('action') if results else None
        }
    
    async def run_all_scenarios(self):
        """Run all test scenarios."""
        print("\n" + "=" * 70)
        print("  WARRANTY ORCHESTRATOR POC - Running All Test Scenarios")
        print("=" * 70)
        print(f"\nTotal scenarios to run: {len(TEST_SCENARIOS)}")
        print("This tests the blue box workflow:")
        print("  Orchestrator → Planner → Warranty Details MCP → Compute → Actions MCP")
        print("-" * 70)
        
        summary = []
        
        for scenario in TEST_SCENARIOS:
            result = await self.run_scenario(scenario)
            summary.append(result)
        
        # Print summary
        print("\n" + "=" * 70)
        print("  SUMMARY")
        print("=" * 70)
        for s in summary:
            status_icon = "✓" if s['final_status'] == 'ok' else "✗"
            print(f"  {status_icon} {s['scenario']}")
            print(f"      Case: {s['case_id']}, Turns: {s['turns']}, Action: {s['final_action']}")
        print("=" * 70 + "\n")
    
    async def interactive_mode(self):
        """Run in interactive mode with pre-populated data."""
        print("\n" + "=" * 70)
        print("  WARRANTY ORCHESTRATOR POC - Interactive Mode")
        print("=" * 70)
        print("\nThis mode pre-populates dummy data so you can focus on testing the workflow.")
        print("\nAvailable Products:")
        for pid, prod in DUMMY_PRODUCTS.items():
            warranty = "✓ WARRANTY" if prod['warranty_active'] else "✗ NO WARRANTY"
            print(f"  {pid}: {prod['product_name']} ({prod['product_type']}) [{warranty}]")
        
        print("\nCommands:")
        print("  /product <id>  - Switch product (e.g., /product HEAT-002)")
        print("  /location <type> - Set location: serviceable or non_serviceable")
        print("  /status        - Show current test context")
        print("  /scenarios     - Run all test scenarios")
        print("  /quit          - Exit")
        print("\nType any message to interact with the warranty bot.")
        print("-" * 70 + "\n")
        
        # Default test context
        current_product = "HEAT-001"
        current_customer = "CUST-001"
        current_location = "serviceable"
        case_id = None
        
        while True:
            try:
                user_input = input("YOU: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    parts = user_input.split()
                    cmd = parts[0].lower()
                    
                    if cmd == "/quit" or cmd == "/exit":
                        print("\nGoodbye!")
                        break
                    
                    elif cmd == "/product":
                        if len(parts) > 1 and parts[1] in DUMMY_PRODUCTS:
                            current_product = parts[1]
                            case_id = None  # Reset case
                            prod = DUMMY_PRODUCTS[current_product]
                            print(f"✓ Switched to: {prod['product_name']} ({prod['product_type']})")
                        else:
                            print(f"Available products: {', '.join(DUMMY_PRODUCTS.keys())}")
                        continue
                    
                    elif cmd == "/location":
                        if len(parts) > 1 and parts[1] in DUMMY_LOCATIONS:
                            current_location = parts[1]
                            print(f"✓ Location set to: {current_location}")
                        else:
                            print("Available locations: serviceable, non_serviceable")
                        continue
                    
                    elif cmd == "/status":
                        prod = DUMMY_PRODUCTS[current_product]
                        loc = DUMMY_LOCATIONS[current_location]
                        print(f"\n--- Current Test Context ---")
                        print(f"  Product: {current_product} - {prod['product_name']}")
                        print(f"  Type: {prod['product_type']}")
                        print(f"  Warranty: {'Active' if prod['warranty_active'] else 'Expired'}")
                        print(f"  Location: {loc['city']}, {loc['state']} ({current_location})")
                        print(f"  Case ID: {case_id or 'None'}")
                        print("----------------------------\n")
                        continue
                    
                    elif cmd == "/scenarios":
                        await self.run_all_scenarios()
                        continue
                    
                    elif cmd == "/reset":
                        case_id = None
                        print("✓ Case reset")
                        continue
                    
                    else:
                        print("Unknown command. Use /quit, /product, /location, /status, /scenarios")
                        continue
                
                # Process message through orchestrator
                request = self.build_request(
                    user_message=user_input,
                    customer_id=current_customer,
                    product_id=current_product,
                    location_key=current_location,
                    case_id=case_id
                )
                
                result = await self.orchestrator.process_request(request)
                case_id = result.get("case_id")
                
                print("\n" + "-" * 40)
                print("BOT:", result.get("response", "No response"))
                
                if result.get("action"):
                    print(f"\n[Action: {result['action']}]")
                    if result.get("action_data"):
                        print(f"[Data: {json.dumps(result['action_data'], indent=2)}]")
                
                print("-" * 40 + "\n")
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except EOFError:
                break


async def main():
    """Main entry point."""
    runner = POCRunner()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--scenarios":
            await runner.run_all_scenarios()
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python main.py              - Interactive mode with dummy data")
            print("  python main.py --scenarios  - Run all test scenarios")
            print("  python main.py --help       - Show this help")
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        await runner.interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
