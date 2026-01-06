"""
Case Context Models

Pydantic models for managing case state throughout the warranty workflow.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class ProductType(str, Enum):
    """Product type enumeration."""
    SALT = "SALT"
    HEAT = "HEAT"


class CustomerDecision(str, Enum):
    """Customer decision states."""
    PENDING = "PENDING"
    PROCEED = "PROCEED"
    DECLINE = "DECLINE"


class Location(BaseModel):
    """Customer location model."""
    zip: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    
    def is_complete(self) -> bool:
        """Check if location has enough information."""
        return bool(self.zip) or (bool(self.city) and bool(self.state))


class WarrantyStatus(BaseModel):
    """Warranty status model."""
    active: bool = False
    coverage_types: List[str] = Field(default_factory=list)
    expiration_date: Optional[str] = None
    all_coverage: Dict[str, Any] = Field(default_factory=dict)


class CaseContext(BaseModel):
    """
    Complete case context model.
    
    This model maintains the full state of a warranty case throughout
    the orchestration workflow.
    """
    # Session/case identifiers
    case_id: str = Field(default_factory=lambda: f"CASE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}")
    session_id: Optional[str] = None
    
    # Authentication/registration state
    logged_in: bool = False
    has_registered_products: bool = False
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    
    # Product information
    product_id: Optional[str] = None
    serial_number: Optional[str] = None
    product_type: Optional[ProductType] = None
    product_name: Optional[str] = None
    purchase_date: Optional[str] = None
    
    # Location
    location: Location = Field(default_factory=Location)
    
    # Warranty status
    warranty_status: WarrantyStatus = Field(default_factory=WarrantyStatus)
    
    # Workflow state
    customer_decision: CustomerDecision = CustomerDecision.PENDING
    potential_charges: Optional[float] = None
    territory_checked: Optional[bool] = None
    territory_serviceable: Optional[bool] = None
    
    # Issue details
    issue_description: Optional[str] = None
    user_messages: List[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Channel
    channel: str = "chat"
    
    class Config:
        use_enum_values = True
    
    def update(self, **kwargs) -> "CaseContext":
        """Update context with new values and refresh updated_at."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()
        return self
    
    def add_user_message(self, message: str) -> None:
        """Add a user message to the history."""
        self.user_messages.append(message)
        self.updated_at = datetime.now()
    
    def has_required_info(self) -> bool:
        """Check if all required information is present."""
        has_product = bool(self.product_id or self.serial_number)
        has_location = self.location.is_complete()
        return has_product and has_location
    
    def get_missing_fields(self) -> List[str]:
        """Get list of missing required fields."""
        missing = []
        if not self.product_id and not self.serial_number:
            missing.append("product_id or serial_number")
        if not self.location.is_complete():
            missing.append("location (zip code or city/state)")
        return missing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for tool calls."""
        return {
            "case_id": self.case_id,
            "logged_in": self.logged_in,
            "has_registered_products": self.has_registered_products,
            "customer_id": self.customer_id,
            "product_id": self.product_id,
            "serial_number": self.serial_number,
            "product_type": self.product_type,
            "location": self.location.model_dump() if self.location else {},
            "warranty_status": self.warranty_status.model_dump() if self.warranty_status else {},
            "customer_decision": self.customer_decision,
            "potential_charges": self.potential_charges,
            "territory_checked": self.territory_checked,
            "territory_serviceable": self.territory_serviceable,
            "issue_description": self.issue_description
        }
    
    @classmethod
    def from_request(cls, request: Dict[str, Any]) -> "CaseContext":
        """
        Create a CaseContext from an incoming request.
        
        Expected request format from Copilot Studio:
        {
            "user_message": "...",
            "logged_in": true/false,
            "has_registered_products": true/false,
            "product_id": "...",
            "serial_number": "...",
            "location": {"zip": "...", "city": "...", "state": "..."},
            "channel": "chat"
        }
        """
        location_data = request.get("location", {})
        location = Location(**location_data) if location_data else Location()
        
        return cls(
            logged_in=request.get("logged_in", False),
            has_registered_products=request.get("has_registered_products", False),
            customer_id=request.get("customer_id"),
            customer_name=request.get("customer_name"),
            customer_email=request.get("customer_email"),
            product_id=request.get("product_id"),
            serial_number=request.get("serial_number"),
            location=location,
            channel=request.get("channel", "chat"),
            issue_description=request.get("issue_description")
        )
