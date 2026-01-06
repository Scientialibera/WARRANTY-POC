"""
Unit Tests for Compute Service

Tests deterministic calculations for warranty windows and charges.
"""

import pytest
from datetime import datetime, date
from src.compute.service import (
    calculate_warranty_window,
    calculate_charges,
    calculate_prorated_amount,
    ComputeService
)


class TestWarrantyWindow:
    """Tests for warranty window calculations."""
    
    def test_active_parts_warranty(self):
        """Test that parts warranty is active within coverage period."""
        # Product purchased 6 months ago
        purchase_date = "2025-07-06"  # 6 months before Jan 6, 2026
        result = calculate_warranty_window(
            purchase_date=purchase_date,
            coverage_type="parts",
            product_type="HEAT",
            reference_date="2026-01-06"
        )
        
        assert result["status"] == "ok"
        assert result["data"]["is_active"] is True
        assert result["data"]["coverage_duration_months"] == 36  # HEAT parts warranty
    
    def test_expired_labor_warranty(self):
        """Test that labor warranty expires after 12 months."""
        # Product purchased 18 months ago
        purchase_date = "2024-07-06"
        result = calculate_warranty_window(
            purchase_date=purchase_date,
            coverage_type="labor",
            product_type="HEAT",
            reference_date="2026-01-06"
        )
        
        assert result["status"] == "ok"
        assert result["data"]["is_active"] is False
        assert result["data"]["days_remaining"] == 0
    
    def test_salt_controller_warranty(self):
        """Test SALT controller has 60 month warranty."""
        purchase_date = "2023-01-06"  # 3 years ago
        result = calculate_warranty_window(
            purchase_date=purchase_date,
            coverage_type="controller",
            product_type="SALT",
            reference_date="2026-01-06"
        )
        
        assert result["status"] == "ok"
        assert result["data"]["is_active"] is True
        assert result["data"]["coverage_duration_months"] == 60
    
    def test_invalid_date_format(self):
        """Test error handling for invalid date format."""
        result = calculate_warranty_window(
            purchase_date="not-a-date",
            coverage_type="parts",
            product_type="HEAT"
        )
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_DATE"
    
    def test_unknown_coverage_type(self):
        """Test error for unknown coverage type."""
        result = calculate_warranty_window(
            purchase_date="2025-01-01",
            coverage_type="unknown",
            product_type="HEAT"
        )
        
        assert result["status"] == "error"
        assert result["error_code"] == "UNKNOWN_COVERAGE"


class TestChargeCalculation:
    """Tests for charge calculations."""
    
    def test_full_warranty_coverage(self):
        """Test charges when everything is covered by warranty."""
        warranty_status = {
            "active": True,
            "coverage_types": ["parts", "labor"],
            "all_coverage": {}
        }
        
        result = calculate_charges(
            product_id="HEAT-001",
            product_type="HEAT",
            warranty_status=warranty_status,
            location={"zip": "77001", "state": "TX"}
        )
        
        assert result["status"] == "ok"
        data = result["data"]
        
        # Should have covered items
        assert len(data["covered_items"]) == 2  # parts and labor
        
        # Only service call should be a potential charge
        potential = [c for c in data["potential_charges"] if c["item"] == "Service Call"]
        assert len(potential) == 1
    
    def test_no_warranty_coverage(self):
        """Test charges when nothing is covered."""
        warranty_status = {
            "active": False,
            "coverage_types": [],
            "all_coverage": {}
        }
        
        result = calculate_charges(
            product_id="HEAT-002",
            product_type="HEAT",
            warranty_status=warranty_status,
            location={"zip": "77001", "state": "TX"}
        )
        
        assert result["status"] == "ok"
        data = result["data"]
        
        # Should have no covered items
        assert len(data["covered_items"]) == 0
        
        # Should have charges for labor, parts, and service call
        assert len(data["potential_charges"]) == 3
    
    def test_regional_modifier_california(self):
        """Test that California has higher pricing modifier."""
        warranty_status = {"active": False, "coverage_types": [], "all_coverage": {}}
        
        result_tx = calculate_charges(
            product_id="HEAT-001",
            product_type="HEAT",
            warranty_status=warranty_status,
            location={"state": "TX"}
        )
        
        result_ca = calculate_charges(
            product_id="HEAT-001",
            product_type="HEAT",
            warranty_status=warranty_status,
            location={"state": "CA"}
        )
        
        tx_total = result_tx["data"]["summary"]["total_potential_charges"]
        ca_total = result_ca["data"]["summary"]["total_potential_charges"]
        
        # CA should be 25% higher
        assert ca_total > tx_total
        assert abs(ca_total / tx_total - 1.25) < 0.01
    
    def test_salt_vs_heat_pricing(self):
        """Test that SALT and HEAT have different base pricing."""
        warranty_status = {"active": False, "coverage_types": [], "all_coverage": {}}
        location = {"state": "TX"}
        
        result_salt = calculate_charges(
            product_id="SALT-001",
            product_type="SALT",
            warranty_status=warranty_status,
            location=location
        )
        
        result_heat = calculate_charges(
            product_id="HEAT-001",
            product_type="HEAT",
            warranty_status=warranty_status,
            location=location
        )
        
        # Both should succeed
        assert result_salt["status"] == "ok"
        assert result_heat["status"] == "ok"
        
        # HEAT has higher service call fee
        salt_service = next(c for c in result_salt["data"]["potential_charges"] 
                          if c["item"] == "Service Call")
        heat_service = next(c for c in result_heat["data"]["potential_charges"] 
                          if c["item"] == "Service Call")
        
        assert heat_service["cost"] > salt_service["cost"]
    
    def test_unknown_product_type(self):
        """Test error for unknown product type."""
        result = calculate_charges(
            product_id="UNKNOWN-001",
            product_type="UNKNOWN",
            warranty_status={},
            location={}
        )
        
        assert result["status"] == "error"
        assert result["error_code"] == "UNKNOWN_PRODUCT_TYPE"


class TestProration:
    """Tests for prorated amount calculations."""
    
    def test_full_coverage_at_start(self):
        """Test 100% coverage at start of warranty."""
        result = calculate_prorated_amount(
            original_amount=1000.00,
            warranty_duration_months=24,
            months_elapsed=0
        )
        
        assert result["status"] == "ok"
        assert result["data"]["proration_percent"] == 100.0
        assert result["data"]["prorated_coverage"] == 1000.00
        assert result["data"]["customer_responsibility"] == 0.00
    
    def test_half_coverage_midway(self):
        """Test 50% coverage halfway through warranty."""
        result = calculate_prorated_amount(
            original_amount=1000.00,
            warranty_duration_months=24,
            months_elapsed=12
        )
        
        assert result["status"] == "ok"
        assert result["data"]["proration_percent"] == 50.0
        assert result["data"]["prorated_coverage"] == 500.00
        assert result["data"]["customer_responsibility"] == 500.00
    
    def test_no_coverage_after_expiry(self):
        """Test 0% coverage after warranty expires."""
        result = calculate_prorated_amount(
            original_amount=1000.00,
            warranty_duration_months=24,
            months_elapsed=30
        )
        
        assert result["status"] == "ok"
        assert result["data"]["proration_percent"] == 0.0
        assert result["data"]["prorated_coverage"] == 0.00
        assert result["data"]["customer_responsibility"] == 1000.00
    
    def test_negative_elapsed_error(self):
        """Test error for negative months elapsed."""
        result = calculate_prorated_amount(
            original_amount=1000.00,
            warranty_duration_months=24,
            months_elapsed=-1
        )
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_ELAPSED"


class TestComputeService:
    """Tests for the ComputeService class."""
    
    def test_service_run_charges(self):
        """Test service.run() for charge calculation."""
        service = ComputeService()
        
        result = service.run({
            "product_id": "HEAT-001",
            "product_type": "HEAT",
            "warranty_status": {"active": True, "coverage_types": ["parts"]},
            "location": {"state": "TX"}
        })
        
        # Should return valid JSON
        import json
        data = json.loads(result)
        
        assert data["status"] == "ok"
        assert "covered_items" in data["data"]
    
    def test_service_run_warranty_window(self):
        """Test service.run() for warranty window calculation."""
        service = ComputeService()
        
        result = service.run({
            "purchase_date": "2025-01-01",
            "coverage_type": "parts",
            "product_type": "HEAT"
        })
        
        import json
        data = json.loads(result)
        
        assert data["status"] == "ok"
        assert "is_active" in data["data"]
    
    def test_service_run_proration(self):
        """Test service.run() for proration calculation."""
        service = ComputeService()
        
        result = service.run({
            "original_amount": 500.00,
            "warranty_duration_months": 24,
            "months_elapsed": 6
        })
        
        import json
        data = json.loads(result)
        
        assert data["status"] == "ok"
        assert "proration_percent" in data["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
