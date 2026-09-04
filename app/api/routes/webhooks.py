"""Razorpay webhook ingestion route."""

from fastapi import APIRouter, Request, Header, HTTPException, Depends
from typing import Optional
from app.schemas.webhook import WebhookProcessingResult
from app.services.webhook_service import WebhookService, WebhookSignatureError

router = APIRouter(tags=["Webhooks"])


def get_webhook_service() -> WebhookService:
    """Dependency injector for WebhookService."""
    return WebhookService()


@router.post("/webhooks/razorpay", response_model=WebhookProcessingResult, summary="Receive Razorpay Webhook")
async def receive_razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: Optional[str] = Header(None, alias="x-razorpay-event-id"),
    service: WebhookService = Depends(get_webhook_service)
) -> WebhookProcessingResult:
    """
    Secure intake endpoint for Razorpay webhook notifications.
    
    Security & Processing Pipeline:
    1. Cryptographic signature verification with HMAC-SHA256.
    2. Idempotency deduplication check.
    3. Payload parsing & entity extraction.
    4. Benchmark schema applicability routing.
    5. Persistent audit trail creation.
    """
    raw_body = await request.body()
    
    if not x_razorpay_signature:
        raise HTTPException(
            status_code=400,
            detail="Missing required 'X-Razorpay-Signature' header"
        )
        
    try:
        result = service.process_webhook(
            raw_body=raw_body,
            signature=x_razorpay_signature,
            event_id_header=x_razorpay_event_id
        )
        return result
    except WebhookSignatureError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal webhook error: {str(e)}")
