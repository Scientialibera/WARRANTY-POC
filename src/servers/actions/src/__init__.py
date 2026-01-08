"""
Actions Integration Module
===========================
Placeholder integration code for MVP phase.

When moving from POC to MVP, this module will contain:
- CRM system integration for case management
- Payment gateway integration
- Service provider directory with real data
- Notification systems (email, SMS)
"""

from .crm_integration import CRMIntegration
from .payment_gateway import PaymentGateway
from .service_directory import ServiceDirectory

__all__ = ["CRMIntegration", "PaymentGateway", "ServiceDirectory"]
