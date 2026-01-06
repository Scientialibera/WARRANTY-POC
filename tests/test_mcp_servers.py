"""
Integration Tests for MCP Servers

Tests the Planner, Warranty Docs, and Actions MCP servers.
"""

import pytest
import json
from src.mcp_servers.planner import generate_plan
from src.mcp_servers.warranty_docs import get_warranty_record, get_warranty_terms
from src.mcp_servers.actions import (
    route_to_queue,
    get_service_directory,
    check_territory,
    generate_paypal_link,
    log_decline_reason,
    notify_next_steps
)


class TestPlannerMCP:
    """Tests for the Planner MCP server."""
    
    def test_not_logged_in_returns_prompt_login(self):
        """Test that unauthenticated users get login prompt."""
        context = {
            "logged_in": False,
            "has_registered_products": False
        }
        
        result = generate_plan(context, "I need help with my product")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        assert len(plan) == 1
        assert plan[0]["step_type"] == "RETURN_ACTION"
        assert plan[0]["action_type"] == "PROMPT_LOGIN"
    
    def test_no_registered_products_returns_prompt(self):
        """Test that users without products get registration prompt."""
        context = {
            "logged_in": True,
            "has_registered_products": False
        }
        
        result = generate_plan(context, "I need help with my product")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        assert plan[0]["step_type"] == "RETURN_ACTION"
        assert plan[0]["action_type"] == "PROMPT_PRODUCT_REGISTRATION"
    
    def test_missing_product_id_asks_for_info(self):
        """Test that missing product_id triggers info request."""
        context = {
            "logged_in": True,
            "has_registered_products": True,
            "product_id": None,
            "location": {"zip": "77001"}
        }
        
        result = generate_plan(context, "I need help")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        assert plan[0]["step_type"] == "ASK_USER_FOR_INFO"
        assert "product_id" in str(plan[0]["required_fields"])
    
    def test_missing_location_asks_for_info(self):
        """Test that missing location triggers info request."""
        context = {
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {}
        }
        
        result = generate_plan(context, "I need help")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        assert plan[0]["step_type"] == "ASK_USER_FOR_INFO"
        assert "location" in str(plan[0]["required_fields"])
    
    def test_complete_context_triggers_warranty_lookup(self):
        """Test that complete context triggers warranty lookup."""
        context = {
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "location": {"zip": "77001"}
        }
        
        result = generate_plan(context, "I need help")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        # First step should be warranty lookup
        assert plan[0]["step_type"] == "CALL_TOOL"
        assert plan[0]["tool_name"] == "get_warranty_record"
    
    def test_salt_warranty_queues_case(self):
        """Test SALT warranty path routes to queue."""
        context = {
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "SALT-001",
            "product_type": "SALT",
            "location": {"zip": "77001"},
            "warranty_status": {"active": True, "coverage_types": ["parts", "labor"]}
        }
        
        result = generate_plan(context, "My softener isn't working")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        
        # Should have queue routing
        queue_step = next((s for s in plan if s.get("tool_name") == "route_to_queue"), None)
        assert queue_step is not None
        assert queue_step["tool_args"]["queue"] == "WarrantySalt"
    
    def test_salt_non_warranty_returns_directory(self):
        """Test SALT non-warranty path returns service directory."""
        context = {
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "SALT-002",
            "product_type": "SALT",
            "location": {"zip": "77001"},
            "warranty_status": {"active": False, "coverage_types": []}
        }
        
        result = generate_plan(context, "My softener needs repair")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        
        # Should have service directory lookup
        dir_step = next((s for s in plan if s.get("tool_name") == "get_service_directory"), None)
        assert dir_step is not None
    
    def test_heat_calculates_charges_first(self):
        """Test HEAT path calculates charges before asking to proceed."""
        context = {
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "product_type": "HEAT",
            "location": {"zip": "77001"},
            "warranty_status": {"active": True, "coverage_types": ["parts"]}
        }
        
        result = generate_plan(context, "My water heater has issues")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        
        # Should calculate charges
        charge_step = next((s for s in plan if s.get("tool_name") == "calculate_charges"), None)
        assert charge_step is not None
    
    def test_heat_decline_logs_reason(self):
        """Test HEAT decline path logs the reason."""
        context = {
            "logged_in": True,
            "has_registered_products": True,
            "product_id": "HEAT-001",
            "product_type": "HEAT",
            "location": {"zip": "77001"},
            "warranty_status": {"active": True, "coverage_types": ["parts"]},
            "potential_charges": 250.00,
            "customer_decision": "DECLINE"
        }
        
        result = generate_plan(context, "No, that's too expensive for me right now")
        
        assert result["status"] == "ok"
        plan = result["data"]["plan"]
        
        # Should log decline reason
        log_step = next((s for s in plan if s.get("tool_name") == "log_decline_reason"), None)
        assert log_step is not None


class TestWarrantyDocsMCP:
    """Tests for the Warranty Docs MCP server."""
    
    def test_get_existing_product(self):
        """Test fetching an existing product record."""
        result = get_warranty_record(product_id="HEAT-001")
        
        assert result["status"] == "ok"
        assert result["data"]["product_type"] == "HEAT"
        assert result["data"]["product_id"] == "HEAT-001"
    
    def test_get_product_by_serial(self):
        """Test fetching product by serial number."""
        result = get_warranty_record(serial_number="SN-SALT-2024-001234")
        
        assert result["status"] == "ok"
        assert result["data"]["product_id"] == "SALT-001"
    
    def test_product_not_found(self):
        """Test error when product doesn't exist."""
        result = get_warranty_record(product_id="NONEXISTENT-001")
        
        assert result["status"] == "error"
        assert result["error_code"] == "PRODUCT_NOT_FOUND"
    
    def test_warranty_status_calculation(self):
        """Test that warranty status is calculated correctly."""
        result = get_warranty_record(product_id="HEAT-001")
        
        assert result["status"] == "ok"
        warranty = result["data"]["warranty_status"]
        
        # HEAT-001 is new (2025-01-01), should have active warranty
        assert warranty["active"] is True
        assert len(warranty["coverage_types"]) > 0
    
    def test_get_warranty_terms(self):
        """Test fetching warranty terms."""
        result = get_warranty_terms()
        
        assert result["status"] == "ok"
        assert "terms" in result["data"]
        assert "WARRANTY TERMS" in result["data"]["terms"]


class TestActionsMCP:
    """Tests for the Actions MCP server."""
    
    def test_route_to_queue(self):
        """Test routing a case to queue."""
        result = route_to_queue(
            queue="WarrantySalt",
            case_context={"product_id": "SALT-001"},
            priority="normal"
        )
        
        assert result["status"] == "ok"
        assert "case_id" in result["data"]
        assert result["data"]["queue"] == "WarrantySalt"
    
    def test_route_to_queue_idempotency(self):
        """Test that idempotency prevents duplicates."""
        idempotency_key = "test-key-123"
        
        result1 = route_to_queue(
            queue="WarrantySalt",
            case_context={"product_id": "SALT-001"},
            idempotency_key=idempotency_key
        )
        
        result2 = route_to_queue(
            queue="WarrantySalt",
            case_context={"product_id": "SALT-001"},
            idempotency_key=idempotency_key
        )
        
        assert result1["data"]["case_id"] == result2["data"]["case_id"]
        assert result2["data"].get("duplicate") is True
    
    def test_get_service_directory(self):
        """Test getting service providers."""
        result = get_service_directory(
            product_type="HEAT",
            location={"zip": "77001"}
        )
        
        assert result["status"] == "ok"
        assert result["data"]["provider_count"] > 0
        assert len(result["data"]["providers"]) > 0
    
    def test_get_service_directory_filters(self):
        """Test service directory with filters."""
        result = get_service_directory(
            product_type="HEAT",
            location={"zip": "77001"},
            filters={"certified_only": True}
        )
        
        assert result["status"] == "ok"
        # All returned providers should be Factory Authorized
        for provider in result["data"]["providers"]:
            assert "Factory Authorized" in provider["certifications"]
    
    def test_check_territory_serviceable(self):
        """Test territory check for serviceable location."""
        result = check_territory(location={"zip": "77001"})
        
        assert result["status"] == "ok"
        assert result["data"]["serviceable"] is True
        assert result["data"]["territory_name"] is not None
    
    def test_check_territory_not_serviceable(self):
        """Test territory check for non-serviceable location."""
        result = check_territory(location={"zip": "90210"})  # Beverly Hills
        
        assert result["status"] == "ok"
        assert result["data"]["serviceable"] is False
    
    def test_generate_paypal_link(self):
        """Test PayPal link generation."""
        result = generate_paypal_link(
            amount=250.00,
            metadata={"case_id": "TEST-001", "product_id": "HEAT-001"}
        )
        
        assert result["status"] == "ok"
        assert "payment_id" in result["data"]
        assert "payment_url" in result["data"]
        assert "sandbox.paypal.com" in result["data"]["payment_url"]
    
    def test_log_decline_reason(self):
        """Test logging decline reason."""
        result = log_decline_reason(
            reason="Too expensive",
            context={"case_id": "TEST-001", "potential_charges": 250.00}
        )
        
        assert result["status"] == "ok"
        assert "log_id" in result["data"]
    
    def test_notify_next_steps(self):
        """Test sending notification."""
        result = notify_next_steps(
            channel="chat",
            template_id="warranty_queued",
            context={
                "case_id": "TEST-001",
                "estimated_response_time": "24 hours"
            }
        )
        
        assert result["status"] == "ok"
        assert result["data"]["status"] == "sent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
