"""Native Razorpay Transaction Risk Service evaluating raw webhook fields."""

import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from app.config import get_settings
from app.storage.audit_store import AuditStore
from razorrisk.engine import RiskDecisionEngine, ModelEvidence, DecisionResult


class NativeRiskService:
    """Service handling feature extraction from raw Razorpay webhooks and native ML inference."""

    MODEL_PATH = "models/razorrisk_native_pipeline.joblib"
    FEATURE_COLUMNS = [
        'amount', 'hour_of_day', 'day_of_week', 'attempts', 'is_international',
        'card_network', 'card_type', 'email_domain'
    ]

    def __init__(self, audit_store: Optional[AuditStore] = None):
        settings = get_settings()
        self.audit_store = audit_store or AuditStore(settings.SQLITE_DB_PATH)
        self.engine = RiskDecisionEngine()
        self.pipeline = None
        
        if os.path.exists(self.MODEL_PATH):
            try:
                self.pipeline = joblib.load(self.MODEL_PATH)
            except Exception as e:
                print(f"Warning: Failed to load native model pipeline: {e}")

    @staticmethod
    def extract_features(payload_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Extract legitimate transaction features from raw Razorpay webhook payload.
        Returns: (success, feature_dict, reason)
        """
        payment_entity = payload_data.get("payment", {}).get("entity", {})
        order_entity = payload_data.get("order", {}).get("entity", {})

        # Require legitimate payment instrument details (e.g. method, card, email, or order)
        method = payment_entity.get("method")
        has_instrument = bool(method or payment_entity.get("card") or payment_entity.get("email") or order_entity.get("attempts"))
        if not has_instrument:
            return False, None, "INSUFFICIENT_TRANSACTION_METADATA"


        # Amount extraction (convert from paise to INR)
        raw_amount = payment_entity.get("amount") or order_entity.get("amount")
        if raw_amount is None:
            return False, None, "MISSING_TRANSACTION_AMOUNT"
        
        try:
            amount_inr = float(raw_amount) / 100.0
            if amount_inr <= 0:
                return False, None, "INVALID_TRANSACTION_AMOUNT"
        except (ValueError, TypeError):
            return False, None, "MALFORMED_TRANSACTION_AMOUNT"


        # Timestamp & cyclic time features
        created_at_epoch = payment_entity.get("created_at") or order_entity.get("created_at")
        if created_at_epoch:
            dt = datetime.fromtimestamp(created_at_epoch, tz=timezone.utc)
            hour_of_day = float(dt.hour)
            day_of_week = float(dt.weekday())
        else:
            now_dt = datetime.now(timezone.utc)
            hour_of_day = float(now_dt.hour)
            day_of_week = float(now_dt.weekday())

        # Velocity / checkout attempts
        attempts = 1.0
        order_attempts = order_entity.get("attempts")
        if order_attempts is not None:
            try:
                attempts = max(1.0, float(order_attempts))
            except (ValueError, TypeError):
                attempts = 1.0

        # International flag
        is_international = 1 if bool(payment_entity.get("international", False)) else 0

        # Card attributes if available
        card_obj = payment_entity.get("card") or {}
        card_network_raw = str(card_obj.get("network") or "other").lower().strip()
        if "visa" in card_network_raw:
            card_network = "visa"
        elif "master" in card_network_raw:
            card_network = "mastercard"
        elif "rupay" in card_network_raw:
            card_network = "rupay"
        elif "discover" in card_network_raw:
            card_network = "discover"
        elif "amex" in card_network_raw:
            card_network = "amex"
        else:
            card_network = "other"

        card_type_raw = str(card_obj.get("type") or "other").lower().strip()
        if "credit" in card_type_raw:
            card_type = "credit"
        elif "debit" in card_type_raw:
            card_type = "debit"
        elif "prepaid" in card_type_raw:
            card_type = "prepaid"
        else:
            card_type = "other"

        # Email domain
        email_str = str(payment_entity.get("email") or "").lower().strip()
        if "@" in email_str:
            domain = email_str.split("@")[-1]
            top_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'anonymous.com', 'outlook.com', 'aol.com', 'comcast.net']
            email_domain = domain if domain in top_domains else 'other'
        else:
            email_domain = 'missing'

        features = {
            'amount': amount_inr,
            'hour_of_day': hour_of_day,
            'day_of_week': day_of_week,
            'attempts': attempts,
            'is_international': is_international,
            'card_network': card_network,
            'card_type': card_type,
            'email_domain': email_domain
        }

        return True, features, "FEATURES_EXTRACTED"

    def score_webhook_transaction(
        self,
        transaction_id: str,
        features: Dict[str, Any],
        cost_profile: str = "BALANCED"
    ) -> Tuple[DecisionResult, Dict[str, Any]]:
        """
        Run the native ML model and evaluate via RiskDecisionEngine.
        """
        if self.pipeline is None:
            raise RuntimeError("Native model pipeline is not loaded.")

        df_input = pd.DataFrame([features])[self.FEATURE_COLUMNS]

        # Get calibrated prediction probability
        prob = float(self.pipeline.predict_proba(df_input)[0, 1])

        # Estimate uncertainty (based on decision boundary distance)
        # Probabilities close to 0.5 have higher uncertainty
        uncertainty = float(1.0 - 2.0 * abs(prob - 0.5))

        evidence = ModelEvidence(
            transaction_id=transaction_id,
            transaction_amount=float(features['amount']),
            fraud_probability=prob,
            calibrated_probability=prob,
            uncertainty=uncertainty,
            model_version="RazorRisk-Native-v1.0.0"
        )

        decision = self.engine.evaluate(evidence=evidence, profile_name=cost_profile)


        inference_meta = {
            "model_type": "RazorRisk-Native-HistGradientBoosting",
            "source_dataset": "IEEE-CIS Fraud Detection (Defensible Feature Mapping)",
            "calibrated_probability": prob,
            "raw_probability": prob,
            "uncertainty": uncertainty,
            "extracted_features": features
        }

        return decision, inference_meta
