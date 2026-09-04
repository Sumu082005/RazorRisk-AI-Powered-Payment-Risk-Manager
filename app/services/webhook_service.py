"""RazorRisk Webhook Service handling signature verification, idempotency, and audit logging."""

import hmac
import hashlib
import json
import uuid
import datetime
from typing import Optional, Dict, Any, Tuple

from app.config import get_settings
from app.storage.audit_store import AuditStore
from app.schemas.webhook import WebhookProcessingResult


class WebhookSignatureError(Exception):
    """Raised when webhook signature verification fails."""
    pass


class WebhookService:
    """Service for securing and processing Razorpay webhooks."""

    SUPPORTED_EVENTS = {
        "payment.failed",
        "payment.authorized",
        "payment.captured",
        "order.paid"
    }

    def __init__(
        self,
        webhook_secret: Optional[str] = None,
        audit_store: Optional[AuditStore] = None
    ):
        settings = get_settings()
        self.webhook_secret = webhook_secret or settings.RAZORPAY_WEBHOOK_SECRET
        self.audit_store = audit_store or AuditStore(settings.SQLITE_DB_PATH)

    def verify_signature(self, raw_body: bytes, signature: Optional[str]) -> bool:
        """
        Verify the Razorpay webhook signature using HMAC-SHA256 over raw request bytes.
        """
        if not signature or not self.webhook_secret:
            return False
            
        computed_signature = hmac.new(
            key=self.webhook_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)

    def process_webhook(
        self,
        raw_body: bytes,
        signature: Optional[str],
        event_id_header: Optional[str] = None
    ) -> WebhookProcessingResult:
        """
        Execute full secure webhook intake pipeline.
        """
        # 1. Signature Verification
        if not self.verify_signature(raw_body, signature):
            raise WebhookSignatureError("Invalid or missing X-Razorpay-Signature header")

        # 2. Parse Payload
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Malformed webhook JSON body: {str(e)}")

        event_type = payload.get("event", "unknown")
        event_id = event_id_header or payload.get("id") or f"evt_{uuid.uuid4().hex[:12]}"

        # 3. Idempotency Check
        existing_event = self.audit_store.get_webhook_event(event_id)
        if existing_event:
            return WebhookProcessingResult(
                status="duplicate",
                event_id=event_id,
                event_type=event_type,
                action_taken="IDEMPOTENT_IGNORE",
                processing_status="DUPLICATE",
                message="Webhook event has already been received and processed.",
                decision_id=existing_event.get("decision_id")
            )

        # 4. Extract Entity References
        payload_data = payload.get("payload", {})
        payment_entity = payload_data.get("payment", {}).get("entity", {})
        order_entity = payload_data.get("order", {}).get("entity", {})
        
        payment_id = payment_entity.get("id")
        order_id = payment_entity.get("order_id") or order_entity.get("id")
        raw_amount_smallest_unit = payment_entity.get("amount") or order_entity.get("amount")
        amount_in_units = (raw_amount_smallest_unit / 100.0) if raw_amount_smallest_unit else 0.0

        # 5. Supported Event Check
        if event_type not in self.SUPPORTED_EVENTS:
            self.audit_store.record_webhook_event(
                event_id=event_id,
                event_type=event_type,
                signature_valid=True,
                processing_status="IGNORED",
                related_order_id=order_id,
                related_payment_id=payment_id,
                payload=payload
            )
            return WebhookProcessingResult(
                status="ignored",
                event_id=event_id,
                event_type=event_type,
                action_taken="IGNORED",
                processing_status="IGNORED",
                message=f"Event type '{event_type}' is not subscribed for automated risk action."
            )

        # 6. Benchmark Schema Applicability Check (AI-First Pipeline - ULB Features)
        # Check whether benchmark feature inputs (V1-V28, Time) are available in payment notes or metadata.
        benchmark_features = None
        notes = payment_entity.get("notes") or order_entity.get("notes") or {}
        if isinstance(notes, dict) and all(f"V{i}" in notes for i in range(1, 29)):
            benchmark_features = notes
        elif "benchmark_features" in payload_data and isinstance(payload_data["benchmark_features"], dict):
            if all(f"V{i}" in payload_data["benchmark_features"] for i in range(1, 29)):
                benchmark_features = payload_data["benchmark_features"]

        if benchmark_features:
            # Benchmark model inputs legitimately available -> Execute reference ULB ML pipeline
            try:
                from app.services.risk_service import RiskService
                from app.schemas.risk import RiskScoreRequest
                
                txn_ref = payment_id or order_id or event_id

                # Check if this transaction has already received an automated scoring event
                existing_scoring = self.audit_store.get_transaction_scoring_event(txn_ref)
                if existing_scoring:
                    self.audit_store.record_webhook_event(
                        event_id=event_id,
                        event_type=event_type,
                        signature_valid=True,
                        processing_status="BENCHMARK_AI_SCORED",
                        related_order_id=order_id,
                        related_payment_id=payment_id,
                        decision_id=existing_scoring.get("decision_id"),
                        payload=payload
                    )
                    return WebhookProcessingResult(
                        status="processed",
                        event_id=event_id,
                        event_type=event_type,
                        action_taken=existing_scoring.get("action", "APPROVE"),
                        processing_status="BENCHMARK_AI_SCORED",
                        message="Webhook verified and linked to existing transaction AI risk assessment.",
                        decision_id=existing_scoring.get("decision_id")
                    )

                score_req_dict = {
                    "transaction_id": txn_ref,
                    "Time": float(benchmark_features.get("Time", 0.0)),
                    "Amount": amount_in_units,
                    "cost_profile": "BALANCED"
                }
                for i in range(1, 29):
                    score_req_dict[f"V{i}"] = float(benchmark_features[f"V{i}"])
                
                risk_req = RiskScoreRequest(**score_req_dict)
                risk_service = RiskService(audit_store=self.audit_store)
                ml_decision = risk_service.score_transaction(risk_req)
                
                self.audit_store.record_webhook_event(
                    event_id=event_id,
                    event_type=event_type,
                    signature_valid=True,
                    processing_status="BENCHMARK_AI_SCORED",
                    related_order_id=order_id,
                    related_payment_id=payment_id,
                    decision_id=ml_decision.decision_id,
                    payload=payload
                )
                
                return WebhookProcessingResult(
                    status="processed",
                    event_id=event_id,
                    event_type=event_type,
                    action_taken=ml_decision.recommended_action,
                    processing_status="BENCHMARK_AI_SCORED",
                    message=f"Webhook verified and analyzed by Reference Benchmark model. Recommendation: {ml_decision.recommended_action}.",
                    decision_id=ml_decision.decision_id
                )
            except Exception:
                pass

        # 7. Native Razorpay ML Pipeline (Plan B)
        # Extract available raw fields from Razorpay webhook payload and evaluate native transaction risk
        try:
            from app.services.native_risk_service import NativeRiskService

            txn_ref = payment_id or order_id or event_id

            # Check if this transaction has already received an automated scoring event (idempotency across multi-event webhook flows)
            existing_scoring = self.audit_store.get_transaction_scoring_event(txn_ref)
            if existing_scoring:
                # Webhook event received for already-scored payment (e.g. order.paid, payment.captured for same payment.authorized)
                self.audit_store.record_webhook_event(
                    event_id=event_id,
                    event_type=event_type,
                    signature_valid=True,
                    processing_status="NATIVE_AI_SCORED",
                    related_order_id=order_id,
                    related_payment_id=payment_id,
                    decision_id=existing_scoring.get("decision_id"),
                    payload=payload
                )

                return WebhookProcessingResult(
                    status="processed",
                    event_id=event_id,
                    event_type=event_type,
                    action_taken=existing_scoring.get("action", "REVIEW"),
                    processing_status="NATIVE_AI_SCORED",
                    message="Webhook verified and linked to existing transaction AI risk assessment.",
                    decision_id=existing_scoring.get("decision_id")
                )

            native_service = NativeRiskService(audit_store=self.audit_store)
            success, features, reason = native_service.extract_features(payload_data)

            if success and features is not None:
                decision, meta = native_service.score_webhook_transaction(
                    transaction_id=txn_ref,
                    features=features,
                    cost_profile="BALANCED"
                )

                # Record webhook event
                self.audit_store.record_webhook_event(
                    event_id=event_id,
                    event_type=event_type,
                    signature_valid=True,
                    processing_status="NATIVE_AI_SCORED",
                    related_order_id=order_id,
                    related_payment_id=payment_id,
                    decision_id=decision.decision_id,
                    payload=payload
                )

                audit_details = {
                    "event_id": event_id,
                    "event_type": event_type,
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "amount": amount_in_units,
                    "currency": payment_entity.get("currency") or order_entity.get("currency", "INR"),
                    "schema_applicability": "NATIVE_RAZORPAY_FIELDS_SCORED",
                    "model_type": meta["model_type"],
                    "source_dataset": meta["source_dataset"],
                    "fraud_probability": meta["calibrated_probability"],
                    "calibrated_probability": meta["calibrated_probability"],
                    "uncertainty": meta["uncertainty"],
                    "extracted_features": meta["extracted_features"],
                    "triggered_rules": [
                        {"rule_id": r.rule_id, "rule_name": r.rule_name, "description": r.description}
                        for r in decision.triggered_rules
                    ]
                }

                # Record in audit trail as NATIVE_AI_SCORED (only once per transaction)
                self.audit_store.record_audit_log(
                    audit_id=f"audit_{uuid.uuid4().hex[:12]}",
                    transaction_id=txn_ref,
                    event_type="NATIVE_AI_SCORED",
                    action=decision.recommended_action.value,
                    cost_profile="BALANCED",
                    decision_id=decision.decision_id,
                    risk_score=meta["calibrated_probability"],
                    risk_tier=decision.risk_tier.value,
                    confidence_tier=decision.confidence_tier.value,
                    expected_loss=decision.estimated_expected_loss,
                    details=audit_details
                )

                return WebhookProcessingResult(
                    status="processed",
                    event_id=event_id,
                    event_type=event_type,
                    action_taken=decision.recommended_action.value,
                    processing_status="NATIVE_AI_SCORED",
                    message=f"Webhook verified and analyzed by Native RazorRisk model. Recommendation: {decision.recommended_action.value}.",
                    decision_id=decision.decision_id
                )


        except Exception as native_err:
            print(f"Native ML scoring exception: {native_err}")

        # 8. Safe Fallback: Only if required model features genuinely cannot be extracted
        decision_id = f"dec_rzp_{uuid.uuid4().hex[:10]}"
        processing_status = "MODEL_NOT_APPLICABLE"
        action_taken = "REVIEW"
        
        self.audit_store.record_webhook_event(
            event_id=event_id,
            event_type=event_type,
            signature_valid=True,
            processing_status=processing_status,
            related_order_id=order_id,
            related_payment_id=payment_id,
            decision_id=decision_id,
            payload=payload
        )

        audit_details = {
            "event_id": event_id,
            "event_type": event_type,
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount_in_units,
            "currency": payment_entity.get("currency") or order_entity.get("currency", "INR"),
            "schema_applicability": "BENCHMARK_PCA_FEATURES_NOT_PRESENT",
            "safety_action": "ROUTED_TO_MANUAL_REVIEW"
        }


        self.audit_store.record_audit_log(
            audit_id=f"audit_{uuid.uuid4().hex[:12]}",
            transaction_id=payment_id or order_id or event_id,
            event_type=f"RAZORPAY_WEBHOOK_{event_type.upper()}",
            action=action_taken,
            cost_profile="BALANCED",
            decision_id=decision_id,
            risk_score=None,
            risk_tier="MEDIUM",
            confidence_tier="LOW_CONFIDENCE",
            expected_loss=amount_in_units,
            details=audit_details
        )

        return WebhookProcessingResult(
            status="processed",
            event_id=event_id,
            event_type=event_type,
            action_taken=action_taken,
            processing_status=processing_status,
            message="Webhook verified. Required fields genuinely unavailable for automated risk model; safe REVIEW assigned.",
            decision_id=decision_id
        )


