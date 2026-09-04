"""Isolated Razorpay API Client (Test Mode)."""

import httpx
from typing import Optional, Dict, Any
from app.config import get_settings


class RazorpayClient:
    """Client for interacting with Razorpay v1 REST API using Basic Auth."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 10.0
    ):
        settings = get_settings()
        self.key_id = key_id or settings.RAZORPAY_KEY_ID
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        self.base_url = (base_url or settings.RAZORPAY_BASE_URL).rstrip("/")
        self.timeout = timeout

    def _get_auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(self.key_id, self.key_secret)

    def create_order(
        self,
        amount: int,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new payment order via POST /v1/orders.
        Amount must be in the smallest currency unit (e.g., paise).
        """
        url = f"{self.base_url}/orders"
        payload = {
            "amount": amount,
            "currency": currency.upper()
        }
        if receipt:
            payload["receipt"] = receipt
        if notes:
            payload["notes"] = notes

        with httpx.Client(auth=self._get_auth(), timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Retrieve order details via GET /v1/orders/{order_id}."""
        url = f"{self.base_url}/orders/{order_id}"
        with httpx.Client(auth=self._get_auth(), timeout=self.timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """Retrieve payment details via GET /v1/payments/{payment_id}."""
        url = f"{self.base_url}/payments/{payment_id}"
        with httpx.Client(auth=self._get_auth(), timeout=self.timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
