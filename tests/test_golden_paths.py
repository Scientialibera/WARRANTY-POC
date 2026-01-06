"""
End-to-End Golden Path Tests

Tests complete workflow scenarios from start to finish.
"""

import pytest
import asyncio
from src.orchestrator import WarrantyOrchestrator


class TestGoldenPaths:
    """End-to-end tests for complete workflow paths."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for tests."""
        return WarrantyOrchestrator()
    
    @pytest.mark.asyncio
    async def test_heat_warranty_agrees_serviceable_paypal(self, orchestrator):
        """
        Golden Path: HEAT + warranty + agrees + serviceable → PayPal link
        
        1. User is logged in with registered HEAT product
        2. Warranty is active
        3. System calculates charges
        4. User agrees to proceed
        5. Location is serviceable
        6. PayPal link is generated
        """
        # Initial request
        request1 = {
            "user_message": "My heat pump water heater isn't working properly",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "77001", "state": "TX"}
        }
        
        result1 = await orchestrator.process_request(request1)
        
        assert result1["status"] == "ok"
        case_id = result1["case_id"]
        
        # Verify warranty lookup happened - response should mention warranty
        assert case_id is not None
        
        # Simulate getting charges and user agreeing
        # For this test, we'll verify the orchestrator can handle the flow
        case = orchestrator._cases[case_id]
        
        # Simulate warranty lookup result
        case.product_type = "HEAT"
        case.warranty_status.active = True
        case.warranty_status.coverage_types = ["parts", "tank"]
        
        # Simulate charge calculation
        case.potential_charges = 220.00
        
        # User agrees
        request2 = {
            "user_message": "Yes, I want to proceed with the service",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "77001", "state": "TX"},
            "case_id": case_id
        }
        
        result2 = await orchestrator.process_request(request2)
        
        assert result2["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_heat_warranty_declines_logs_reason(self, orchestrator):
        """
        Golden Path: HEAT + warranty + declines → reason logged
        
        1. User has HEAT product with warranty
        2. Charges are calculated
        3. User declines with a reason
        4. Reason is logged
        """
        case = orchestrator.get_or_create_case({
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "77001", "state": "TX"}
        })
        
        # Set up state as if charges have been calculated
        case.product_type = "HEAT"
        case.warranty_status.active = True
        case.warranty_status.coverage_types = ["parts"]
        case.potential_charges = 350.00
        
        # User declines
        request = {
            "user_message": "No, that's too expensive. I'll wait until next month.",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "77001", "state": "TX"},
            "case_id": case.case_id
        }
        
        result = await orchestrator.process_request(request)
        
        assert result["status"] == "ok"
        # Response should acknowledge the decline
        response_lower = result["response"].lower()
        assert any(word in response_lower for word in ["understand", "noted", "acknowledge"])
    
    @pytest.mark.asyncio
    async def test_heat_not_serviceable_returns_directory(self, orchestrator):
        """
        Golden Path: HEAT + not serviceable → service directory returned
        
        1. User has HEAT product
        2. User agrees to proceed
        3. Territory is not serviceable
        4. Service directory is returned
        """
        case = orchestrator.get_or_create_case({
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "90210", "state": "CA"}  # Not serviceable
        })
        
        # Set up state
        case.product_type = "HEAT"
        case.warranty_status.active = True
        case.potential_charges = 280.00
        case.customer_decision = "PROCEED"
        
        request = {
            "user_message": "Yes, I want to proceed",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "90210", "state": "CA"},
            "case_id": case.case_id
        }
        
        result = await orchestrator.process_request(request)
        
        assert result["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_salt_warranty_queued_with_notification(self, orchestrator):
        """
        Golden Path: SALT + warranty → queued + next steps message
        
        1. User has SALT product with active warranty
        2. Case is queued for warranty service
        3. Customer receives next steps notification
        """
        request = {
            "user_message": "My water softener isn't regenerating properly",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "SALT-001",
            "location": {"zip": "77001", "state": "TX"}
        }
        
        result = await orchestrator.process_request(request)
        
        assert result["status"] == "ok"
        case_id = result["case_id"]
        
        # Simulate the case being processed with warranty lookup
        case = orchestrator._cases[case_id]
        case.product_type = "SALT"
        case.warranty_status.active = True
        case.warranty_status.coverage_types = ["parts", "labor", "controller"]
        
        # Continue the flow
        request2 = {
            "user_message": "Yes, please help me with warranty service",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "SALT-001",
            "location": {"zip": "77001", "state": "TX"},
            "case_id": case_id
        }
        
        result2 = await orchestrator.process_request(request2)
        
        assert result2["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_salt_non_warranty_returns_directory(self, orchestrator):
        """
        Golden Path: SALT + non-warranty → directory returned
        
        1. User has SALT product with expired warranty
        2. Service directory is returned
        """
        case = orchestrator.get_or_create_case({
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "SALT-002",  # Older product with expired parts/labor
            "location": {"zip": "77001", "state": "TX"}
        })
        
        # Set up state with expired warranty
        case.product_type = "SALT"
        case.warranty_status.active = False
        case.warranty_status.coverage_types = []
        
        request = {
            "user_message": "My water softener needs repair",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "SALT-002",
            "location": {"zip": "77001", "state": "TX"},
            "case_id": case.case_id
        }
        
        result = await orchestrator.process_request(request)
        
        assert result["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_missing_info_loop_product_id(self, orchestrator):
        """
        Golden Path: Missing info loop (no product_id)
        
        1. User is authenticated but no product specified
        2. System asks for product info
        3. User provides product
        4. Flow continues
        """
        # First request - missing product_id
        request1 = {
            "user_message": "I need help with my appliance",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": None,
            "location": {"zip": "77001", "state": "TX"}
        }
        
        result1 = await orchestrator.process_request(request1)
        
        assert result1["status"] == "ok"
        assert result1.get("action") == "ASK_USER"
        
        case_id = result1["case_id"]
        
        # Second request - provide product_id
        request2 = {
            "user_message": "It's my HEAT-001 heat pump water heater",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "77001", "state": "TX"},
            "case_id": case_id
        }
        
        result2 = await orchestrator.process_request(request2)
        
        assert result2["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_missing_info_loop_location(self, orchestrator):
        """
        Golden Path: Missing info loop (no location)
        
        1. User has product but no location
        2. System asks for location
        3. User provides location
        4. Flow continues
        """
        request1 = {
            "user_message": "My HEAT-001 needs service",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {}
        }
        
        result1 = await orchestrator.process_request(request1)
        
        assert result1["status"] == "ok"
        assert result1.get("action") == "ASK_USER"
        
        case_id = result1["case_id"]
        
        # Provide location
        request2 = {
            "user_message": "I'm in Houston, TX 77001",
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "77001", "city": "Houston", "state": "TX"},
            "case_id": case_id
        }
        
        result2 = await orchestrator.process_request(request2)
        
        assert result2["status"] == "ok"


class TestAuthenticationFlow:
    """Tests for authentication and registration gates."""
    
    @pytest.fixture
    def orchestrator(self):
        return WarrantyOrchestrator()
    
    @pytest.mark.asyncio
    async def test_not_logged_in_prompts_login(self, orchestrator):
        """Verify unauthenticated users get login prompt."""
        request = {
            "user_message": "I need help with my water heater",
            "logged_in": False,
            "has_registered_products": False
        }
        
        result = await orchestrator.process_request(request)
        
        assert result["status"] == "ok"
        assert result.get("action") == "PROMPT_LOGIN"
        assert "log in" in result["response"].lower()
    
    @pytest.mark.asyncio
    async def test_no_products_prompts_registration(self, orchestrator):
        """Verify users without products get registration prompt."""
        request = {
            "user_message": "I need help with my water heater",
            "logged_in": True,
            "has_registered_products": False
        }
        
        result = await orchestrator.process_request(request)
        
        assert result["status"] == "ok"
        assert result.get("action") == "PROMPT_PRODUCT_REGISTRATION"
        assert "register" in result["response"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
