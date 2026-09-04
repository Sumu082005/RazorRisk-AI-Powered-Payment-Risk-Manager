"""Razorpay order and payment management routes."""

from fastapi import APIRouter, HTTPException, Depends
import httpx
from app.config import get_settings
from app.schemas.razorpay import CreateOrderRequest, CreateOrderResponse
from app.services.razorpay_client import RazorpayClient

router = APIRouter(prefix="/api/v1/razorpay", tags=["Razorpay Integration"])


def get_razorpay_client() -> RazorpayClient:
    """Dependency injector for RazorpayClient."""
    return RazorpayClient()


@router.post("/orders", response_model=CreateOrderResponse, summary="Create Razorpay Order")
async def create_order(
    request: CreateOrderRequest,
    client: RazorpayClient = Depends(get_razorpay_client)
) -> CreateOrderResponse:
    """
    Create a new payment order with Razorpay Test Mode API.
    Returns sanitized order details and public key ID. NEVER returns secrets.
    """
    settings = get_settings()
    try:
        order_data = client.create_order(
            amount=request.amount,
            currency=request.currency,
            receipt=request.receipt,
            notes=request.notes
        )
        return CreateOrderResponse(
            order_id=order_data["id"],
            amount=order_data["amount"],
            currency=order_data["currency"],
            receipt=order_data.get("receipt"),
            status=order_data.get("status", "created"),
            key_id=settings.RAZORPAY_KEY_ID
        )
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        error_detail = e.response.text
        raise HTTPException(status_code=status_code, detail=f"Razorpay API Error: {error_detail}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


@router.get("/orders/{order_id}", summary="Get Razorpay Order Details")
async def get_order(
    order_id: str,
    client: RazorpayClient = Depends(get_razorpay_client)
):
    """Retrieve order details from Razorpay."""
    try:
        return client.get_order(order_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payments/{payment_id}", summary="Get Razorpay Payment Details")
async def get_payment(
    payment_id: str,
    client: RazorpayClient = Depends(get_razorpay_client)
):
    """Retrieve payment details from Razorpay."""
    try:
        return client.get_payment(payment_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
