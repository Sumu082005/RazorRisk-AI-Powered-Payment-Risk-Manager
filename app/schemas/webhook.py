"""Pydantic schemas for Razorpay webhook processing."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class WebhookProcessingResult(BaseModel):
    """Response payload for webhook receiver."""
    
    status: str = Field(..., description="Processing status: 'processed', 'duplicate', 'ignored', 'failed'")
    event_id: str
    event_type: str
    action_taken: str = Field(..., description="Action taken: 'APPROVE', 'REVIEW', 'BLOCK', 'IGNORED'")
    processing_status: str
    message: str
    decision_id: Optional[str] = None
