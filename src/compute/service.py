"""
Compute Service

Deterministic calculation service for warranty-related computations:
- Date calculations (warranty windows, coverage periods)
- Charge calculations (covered vs non-covered items)
- Prorated amounts for partial warranty coverage

All calculations are deterministic: same input → same output.
"""

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Any, Dict, Optional
import json


# Base service charges by product type
BASE_CHARGES = {
    "SALT": {
        "service_call": 95.00,
        "labor_hourly": 85.00,
        "parts": {
            "valve_assembly": 245.00,
            "control_board": 189.00,
            "brine_tank": 175.00,
            "resin_bed": 325.00,
            "motor": 215.00,
            "general_parts": 75.00
        },
        "average_labor_hours": 2.0
    },
    "HEAT": {
        "service_call": 125.00,
        "labor_hourly": 95.00,
        "parts": {
            "compressor": 850.00,
            "heat_exchanger": 425.00,
            "control_board": 275.00,
            "heating_element": 195.00,
            "thermostat": 85.00,
            "tank_replacement": 1200.00,
            "general_parts": 100.00
        },
        "average_labor_hours": 3.0
    }
}

# Regional modifiers for pricing
REGIONAL_MODIFIERS = {
    "TX": 1.0,  # Texas - base rate
    "CA": 1.25, # California - 25% higher
    "NY": 1.20, # New York - 20% higher
    "FL": 1.05, # Florida - 5% higher
    "default": 1.0
}


def calculate_warranty_window(
    purchase_date: str,
    coverage_type: str,
    product_type: str,
    reference_date: str = None
) -> Dict[str, Any]:
    """
    Calculate warranty window and current status.
    
    Args:
        purchase_date: Date of purchase (YYYY-MM-DD)
        coverage_type: Type of coverage (parts, labor, controller, tank)
        product_type: SALT or HEAT
        reference_date: Date to check against (defaults to today)
        
    Returns:
        Dictionary with warranty window details
    """
    # Coverage durations in months
    coverage_durations = {
        "SALT": {
            "parts": 24,
            "labor": 12,
            "controller": 60
        },
        "HEAT": {
            "parts": 36,
            "labor": 12,
            "tank": 120
        }
    }
    
    try:
        purchase = datetime.strptime(purchase_date, "%Y-%m-%d").date()
    except ValueError:
        return {
            "status": "error",
            "error_code": "INVALID_DATE",
            "message": f"Invalid purchase date format: {purchase_date}"
        }
    
    ref_date = date.today()
    if reference_date:
        try:
            ref_date = datetime.strptime(reference_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    durations = coverage_durations.get(product_type, {})
    duration_months = durations.get(coverage_type, 0)
    
    if duration_months == 0:
        return {
            "status": "error",
            "error_code": "UNKNOWN_COVERAGE",
            "message": f"Unknown coverage type '{coverage_type}' for product type '{product_type}'"
        }
    
    expiration = purchase + relativedelta(months=duration_months)
    days_until_expiration = (expiration - ref_date).days
    is_active = days_until_expiration > 0
    
    return {
        "status": "ok",
        "data": {
            "coverage_type": coverage_type,
            "product_type": product_type,
            "purchase_date": purchase_date,
            "coverage_duration_months": duration_months,
            "expiration_date": expiration.isoformat(),
            "is_active": is_active,
            "days_remaining": max(0, days_until_expiration),
            "reference_date": ref_date.isoformat()
        }
    }


def calculate_charges(
    product_id: str,
    product_type: str,
    warranty_status: Dict[str, Any],
    location: Dict[str, str],
    issue_description: str = None
) -> Dict[str, Any]:
    """
    Calculate potential service charges based on warranty coverage.
    
    Args:
        product_id: Product identifier
        product_type: SALT or HEAT
        warranty_status: Current warranty status object
        location: Customer location with zip, city, state
        issue_description: Optional description of the issue
        
    Returns:
        Dictionary with charge breakdown
    """
    if product_type not in BASE_CHARGES:
        return {
            "status": "error",
            "error_code": "UNKNOWN_PRODUCT_TYPE",
            "message": f"Unknown product type: {product_type}"
        }
    
    base = BASE_CHARGES[product_type]
    
    # Get regional modifier
    state = location.get("state", "").upper()
    regional_modifier = REGIONAL_MODIFIERS.get(state, REGIONAL_MODIFIERS["default"])
    
    # Extract warranty coverage
    all_coverage = warranty_status.get("all_coverage", {})
    active_coverages = warranty_status.get("coverage_types", [])
    
    # Determine what's covered
    parts_covered = "parts" in active_coverages
    labor_covered = "labor" in active_coverages
    
    # Calculate charges
    service_call_charge = base["service_call"]
    
    # Labor charges (if not covered)
    labor_hours = base["average_labor_hours"]
    labor_rate = base["labor_hourly"]
    labor_charge = 0 if labor_covered else (labor_hours * labor_rate)
    
    # Parts charges (estimated average - if not covered)
    parts_charge = 0 if parts_covered else base["parts"]["general_parts"]
    
    # Apply regional modifier
    subtotal = service_call_charge + labor_charge + parts_charge
    adjusted_total = round(subtotal * regional_modifier, 2)
    
    # Build charge breakdown
    covered_items = []
    potential_charges = []
    
    if labor_covered:
        covered_items.append({
            "item": "Labor",
            "original_cost": round(labor_hours * labor_rate * regional_modifier, 2),
            "covered_by": "labor warranty"
        })
    else:
        potential_charges.append({
            "item": "Labor",
            "cost": round(labor_hours * labor_rate * regional_modifier, 2),
            "description": f"{labor_hours} hours @ ${labor_rate}/hr"
        })
    
    if parts_covered:
        covered_items.append({
            "item": "Parts",
            "original_cost": round(base["parts"]["general_parts"] * regional_modifier, 2),
            "covered_by": "parts warranty"
        })
    else:
        potential_charges.append({
            "item": "Parts (estimated)",
            "cost": round(base["parts"]["general_parts"] * regional_modifier, 2),
            "description": "Actual parts cost may vary"
        })
    
    potential_charges.append({
        "item": "Service Call",
        "cost": round(service_call_charge * regional_modifier, 2),
        "description": "Standard service call fee"
    })
    
    # Calculate totals
    total_covered = sum(item["original_cost"] for item in covered_items)
    total_potential = sum(item["cost"] for item in potential_charges)
    
    return {
        "status": "ok",
        "data": {
            "product_id": product_id,
            "product_type": product_type,
            "location": location,
            "regional_modifier": regional_modifier,
            "covered_items": covered_items,
            "potential_charges": potential_charges,
            "summary": {
                "total_covered_value": total_covered,
                "total_potential_charges": total_potential,
                "warranty_savings": total_covered
            },
            "assumptions": [
                "Labor hours are estimated at average repair time",
                "Parts costs are estimated - actual may vary based on diagnosis",
                "Service call fee is non-refundable",
                f"Regional pricing modifier applied: {regional_modifier}x"
            ]
        }
    }


def calculate_prorated_amount(
    original_amount: float,
    warranty_duration_months: int,
    months_elapsed: int
) -> Dict[str, Any]:
    """
    Calculate prorated amount for partial warranty coverage.
    
    Args:
        original_amount: Original item cost
        warranty_duration_months: Total warranty duration
        months_elapsed: Months since purchase
        
    Returns:
        Dictionary with prorated calculations
    """
    if months_elapsed < 0:
        return {
            "status": "error",
            "error_code": "INVALID_ELAPSED",
            "message": "Months elapsed cannot be negative"
        }
    
    if warranty_duration_months <= 0:
        return {
            "status": "error",
            "error_code": "INVALID_DURATION",
            "message": "Warranty duration must be positive"
        }
    
    # Calculate proration percentage
    if months_elapsed >= warranty_duration_months:
        proration_percent = 0.0
    else:
        remaining_percent = (warranty_duration_months - months_elapsed) / warranty_duration_months
        proration_percent = remaining_percent * 100
    
    prorated_coverage = round(original_amount * (proration_percent / 100), 2)
    customer_responsibility = round(original_amount - prorated_coverage, 2)
    
    return {
        "status": "ok",
        "data": {
            "original_amount": original_amount,
            "warranty_duration_months": warranty_duration_months,
            "months_elapsed": months_elapsed,
            "proration_percent": round(proration_percent, 1),
            "prorated_coverage": prorated_coverage,
            "customer_responsibility": customer_responsibility
        }
    }


class ComputeService:
    """
    Service class for deterministic warranty computations.
    
    Implements the run(tool_call) interface expected by the MSFT Agent Framework.
    """
    
    def __init__(self):
        """Initialize the compute service."""
        pass
    
    def run(self, tool_call: Dict[str, Any]) -> str:
        """
        Execute a computation based on tool_call parameters.
        
        This method routes to the appropriate calculation function based on
        the parameters provided.
        
        Args:
            tool_call: Dictionary containing calculation parameters
            
        Returns:
            JSON string with calculation results
        """
        # Determine which calculation to perform based on parameters
        if "purchase_date" in tool_call and "coverage_type" in tool_call:
            result = calculate_warranty_window(
                purchase_date=tool_call.get("purchase_date"),
                coverage_type=tool_call.get("coverage_type"),
                product_type=tool_call.get("product_type", "HEAT"),
                reference_date=tool_call.get("reference_date")
            )
        elif "warranty_status" in tool_call:
            result = calculate_charges(
                product_id=tool_call.get("product_id", ""),
                product_type=tool_call.get("product_type", "HEAT"),
                warranty_status=tool_call.get("warranty_status", {}),
                location=tool_call.get("location", {}),
                issue_description=tool_call.get("issue_description")
            )
        elif "original_amount" in tool_call:
            result = calculate_prorated_amount(
                original_amount=tool_call.get("original_amount", 0),
                warranty_duration_months=tool_call.get("warranty_duration_months", 12),
                months_elapsed=tool_call.get("months_elapsed", 0)
            )
        else:
            result = {
                "status": "error",
                "error_code": "UNKNOWN_CALCULATION",
                "message": "Could not determine calculation type from parameters"
            }
        
        return json.dumps(result, indent=2)


# Factory function for service discovery
def get_compute_service() -> ComputeService:
    """Factory function to create a ComputeService instance."""
    return ComputeService()
