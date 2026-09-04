"""Risk Service orchestrating ML Inference and Deterministic Policy Decisioning."""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any

from app.config import get_settings
from app.schemas.risk import RiskScoreRequest, RiskScoreResponse
from app.storage.audit_store import AuditStore
from razorrisk.engine import RiskDecisionEngine, ModelEvidence, DecisionResult


class RiskService:
    """Service handling feature parsing, ML inference, and policy engine execution."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        audit_store: Optional[AuditStore] = None
    ):
        settings = get_settings()
        self.model_path = model_path or settings.MODEL_ARTIFACT_PATH
        self.audit_store = audit_store or AuditStore(settings.SQLITE_DB_PATH)
        self.engine = RiskDecisionEngine()
        
        # Load serialized pipeline artifact
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model artifact not found at path: {self.model_path}")
            
        bundle = joblib.load(self.model_path)
        self.model = bundle["model_object"]
        self.preprocessor = bundle["preprocessor"]
        self.feature_columns = bundle["feature_columns"]
        self.isotonic_calibrator = bundle.get("isotonic_calibrator")
        self.model_version = bundle.get("model_name", "RandomForest-v1.0.0")

    def score_transaction(self, request: RiskScoreRequest) -> RiskScoreResponse:
        """
        Execute full end-to-end risk evaluation for a transaction payload.
        """
        # 1. Format input into DataFrame with exact feature ordering
        feature_dict = request.model_dump(exclude={"transaction_id", "cost_profile"})
        df_input = pd.DataFrame([feature_dict])[self.feature_columns]
        
        # 2. Preprocess numerical features
        X_prep = self.preprocessor.transform(df_input)
        
        # 3. Model Inference (Raw Probability)
        raw_prob = float(self.model.predict_proba(X_prep)[0, 1])
        
        # 4. Calibrated Probability
        calib_prob = None
        if self.isotonic_calibrator is not None:
            calib_prob = float(self.isotonic_calibrator.predict(np.array([raw_prob]))[0])
            
        # 5. Tree Dispersion (Standard Deviation across 100 forest trees)
        tree_preds = np.array([tree.predict_proba(X_prep)[0, 1] for tree in self.model.estimators_])
        tree_std = float(np.std(tree_preds))
        
        # 6. Feature Contributions (Normalized feature weight contributions)
        # Using model feature importances scaled by input feature values
        feature_importances = getattr(self.model, "feature_importances_", None)
        feature_contributions = {}
        if feature_importances is not None:
            for idx, col in enumerate(self.feature_columns):
                # Relative impact proxy: normalized preprocessed magnitude * feature importance
                val = float(X_prep[0, idx])
                feature_contributions[col] = round(val * feature_importances[idx], 4)

        # 7. Construct ModelEvidence
        evidence = ModelEvidence(
            transaction_id=request.transaction_id,
            transaction_amount=request.Amount,
            fraud_probability=raw_prob,
            calibrated_probability=calib_prob,
            tree_dispersion_std=tree_std,
            feature_contributions=feature_contributions,
            raw_features=feature_dict,
            model_version=self.model_version
        )
        
        # 8. Execute Deterministic Policy Engine
        decision: DecisionResult = self.engine.evaluate(
            evidence=evidence,
            profile_name=request.cost_profile
        )
        
        # 9. Record Structured Audit Trail in SQLite Store
        audit_details = {
            **decision.audit_event,
            "amount": request.Amount,
            "currency": "INR",
            "explanation_factors": decision.explanation_factors
        }

        self.audit_store.record_audit_log(
            audit_id=decision.audit_event["audit_event_id"],
            transaction_id=request.transaction_id,
            event_type="INTERNAL_RISK_SCORE",
            action=decision.recommended_action.value,
            cost_profile=decision.cost_profile.value,
            decision_id=decision.decision_id,
            risk_score=decision.risk_score,
            risk_tier=decision.risk_tier.value,
            confidence_tier=decision.confidence_tier.value,
            expected_loss=decision.estimated_expected_loss,
            details=audit_details
        )

        
        # 10. Format and Return Response
        return RiskScoreResponse(
            transaction_id=decision.transaction_id,
            decision_id=decision.decision_id,
            fraud_probability=decision.risk_score,
            calibrated_probability=calib_prob,
            uncertainty=decision.audit_event.get("uncertainty_score", 0.0),
            risk_score=decision.risk_score,
            risk_tier=decision.risk_tier.value,
            confidence_tier=decision.confidence_tier.value,
            recommended_action=decision.recommended_action.value,
            cost_profile=decision.cost_profile.value,
            triggered_rules=[
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "severity": r.severity,
                    "description": r.description
                }
                for r in decision.triggered_rules
            ],
            estimated_expected_loss=decision.estimated_expected_loss,
            explanation_factors=decision.explanation_factors,
            requires_human_review=decision.requires_human_review,
            model_version=decision.model_version,
            policy_version=decision.policy_version,
            decision_timestamp=decision.decision_timestamp
        )
