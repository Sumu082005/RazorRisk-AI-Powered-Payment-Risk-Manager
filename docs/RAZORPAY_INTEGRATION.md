# RazorRisk — Razorpay Webhook Integration & Security Architecture

**Project:** RazorRisk (Razorpay AI Buildathon 2026 — AI Risk Manager Track)  
**Webhook Path:** `POST /webhooks/razorpay`  
**Full Local URL:** `http://localhost:8000/webhooks/razorpay`

---

## 1. Webhook Architecture & Security Pipeline

```
Incoming HTTP POST Request
    │
    ▼
┌───────────────────────────────────────────┐
│ 1. Cryptographic HMAC-SHA256 Verification │  Rejects missing or tampered X-Razorpay-Signature (HTTP 400)
└─────────────────────┬─────────────────────┘
                      │ Valid Signature
                      ▼
┌───────────────────────────────────────────┐
│ 2. Idempotency Deduplication Check        │  Checks SQLite for x-razorpay-event-id
└─────────────────────┬─────────────────────┘
                      │ New Event
                      ▼
┌───────────────────────────────────────────┐
│ 3. Payload Parsing & Entity Normalization │  Extracts payment_id, order_id, amount
└─────────────────────┬─────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────┐
│ 4. Benchmark Schema Applicability Check   │  Raw payment events lack V1-V28 PCA features
└─────────────────────┬─────────────────────┘  => Assigns MODEL_NOT_APPLICABLE status
                      │
                      ▼
┌───────────────────────────────────────────┐
│ 5. Safe Review Routing & Audit Logging    │  Routes to manual REVIEW & writes immutable SQLite audit record
└───────────────────────────────────────────┘
```

---

## 2. Signature Verification Details

Razorpay generates an HMAC-SHA256 signature using the raw HTTP request body and your configured `RAZORPAY_WEBHOOK_SECRET`.

### Implementation:
```python
computed_signature = hmac.new(
    key=RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
    msg=raw_body_bytes,
    digestmod=hashlib.sha256
).hexdigest()

is_valid = hmac.compare_digest(computed_signature, request.headers["X-Razorpay-Signature"])
```

If the signature header is missing or does not match, the request is immediately aborted with `HTTP 400 Bad Request`.

---

## 3. Webhook Idempotency

Razorpay provides a unique event identifier in the request header `x-razorpay-event-id` (or in payload `id`).

### Idempotency Flow:
1. `AuditStore.get_webhook_event(event_id)` queries local SQLite database.
2. If the record exists and has already been processed:
   - Returns `HTTP 200 OK` with payload:
     ```json
     {
       "status": "duplicate",
       "event_id": "evt_NXKj912481",
       "event_type": "payment.captured",
       "action_taken": "IDEMPOTENT_IGNORE",
       "processing_status": "DUPLICATE",
       "message": "Webhook event has already been received and processed."
     }
     ```
   - Prevents double-processing while satisfying Razorpay's webhook acknowledgement requirements.

---

## 4. Supported Webhook Events

| Event Name | Description | Default Risk Action |
|------------|-------------|---------------------|
| `payment.authorized` | Customer completed payment auth; funds held | `REVIEW` (Safe fallback) |
| `payment.captured` | Payment captured successfully | `REVIEW` (Safe fallback) |
| `payment.failed` | Payment failed or declined by issuing bank | `REVIEW` (Audit logging) |
| `order.paid` | Order state updated to paid | `REVIEW` (Audit logging) |
| *All other events* | Unsubscribed notification | `IGNORED` (HTTP 200) |

---

## 5. Known Benchmark vs Razorpay Live Schema Limitation

> [!IMPORTANT]
> **ULB Benchmark Schema vs Live Razorpay Payload:**  
> The machine learning model was trained on the ULB Credit Card Fraud Detection benchmark dataset which requires 30 numerical variables (`Time`, `Amount`, `V1` through `V28`).  
> 
> A standard Razorpay Test Mode webhook contains transactional payment metadata (`payment_id`, `order_id`, `amount`, `currency`, `method`, `bank`, `email`, `contact`) but **does not contain the anonymized V1–V28 PCA features**.
> 
> **Design Principle:** RazorRisk **never fabricates V1–V28 feature values**. When a raw Razorpay webhook arrives, the system sets `processing_status = "MODEL_NOT_APPLICABLE"`, assigns a safe `REVIEW` state, logs the full audit event, and avoids running invalid mock inference.

---

## 6. Local Testing with Curl

### Simulating a Valid Webhook Event:
```bash
# Python one-liner to generate HMAC signature and send test webhook
python -c "
import hmac, hashlib, json, httpx

secret = 'placeholder_webhook_secret'
payload = {
    'entity': 'event',
    'event': 'payment.authorized',
    'payload': {
        'payment': {
            'entity': {
                'id': 'pay_test_12345',
                'amount': 50000,
                'currency': 'INR',
                'order_id': 'order_test_999'
            }
        }
    }
}
body = json.dumps(payload).encode('utf-8')
sig = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

resp = httpx.post(
    'http://localhost:8000/webhooks/razorpay',
    content=body,
    headers={
        'Content-Type': 'application/json',
        'X-Razorpay-Signature': sig,
        'x-razorpay-event-id': 'evt_local_001'
    }
)
print('Status:', resp.status_code)
print('Response:', resp.json())
"
```
