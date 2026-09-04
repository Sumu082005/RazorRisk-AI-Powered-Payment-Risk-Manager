"""Pydantic schemas for Razorpay order and payment operations."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class CreateOrderRequest(BaseModel):
    """Input payload for creating a Razorpay Test Mode order."""
    
    amount: int = Field(..., ge=100, le=10000000, description="Order amount in smallest currency unit / paise (min 100 paise = ₹1, max 10,000,000 paise = ₹1,00,000)")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="3-letter ISO currency code")
    receipt: Optional[str] = Field(default=None, max_length=40, description="Internal receipt / tracking ID")
    notes: Optional[Dict[str, str]] = Field(default_factory=dict, description="Arbitrary metadata key-value pairs")


    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ["INR", "USD", "EUR", "GBP", "SGD", "AED"]:
            raise ValueError(f"Currency '{v}' is not currently supported")
        return upper


class CreateOrderResponse(BaseModel):
    """Sanitized order response. NEVER exposes secret credentials."""
    
    order_id: str
    amount: int
    currency: str
    receipt: Optional[str] = None
    status: str
    key_id: str = Field(..., description="Public Razorpay Key ID for frontend checkout")
