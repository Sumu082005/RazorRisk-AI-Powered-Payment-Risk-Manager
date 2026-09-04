"""Practical and Defensible Uncertainty & Confidence Tiering for RazorRisk."""

from typing import Tuple, Optional
from razorrisk.engine.types import ConfidenceTier, ModelEvidence


def compute_uncertainty_score(
    fraud_prob: float,
    calibrated_prob: Optional[float] = None,
    tree_std: Optional[float] = None,
    block_threshold: float = 0.34
) -> float:
    """
    Compute a normalized uncertainty metric U in [0.0, 1.0].
    
    Factors:
    1. Distance from the operational decision boundary: Close to threshold => high uncertainty.
    2. Divergence between raw and calibrated probabilities: High gap => calibration uncertainty.
    3. Tree prediction dispersion (standard deviation across individual forest estimators).
    """
    p = max(0.0, min(1.0, fraud_prob))
    
    # 1. Proximity to decision boundary (max uncertainty at p == threshold)
    dist_to_boundary = abs(p - block_threshold)
    boundary_uncertainty = max(0.0, 1.0 - (dist_to_boundary / 0.30))
    
    # 2. Calibration discrepancy
    calib_uncertainty = 0.0
    if calibrated_prob is not None:
        p_cal = max(0.0, min(1.0, calibrated_prob))
        calib_gap = abs(p - p_cal)
        calib_uncertainty = min(1.0, calib_gap / 0.20)
        
    # 3. Tree dispersion uncertainty
    dispersion_uncertainty = 0.0
    if tree_std is not None:
        # Theoretical max std for binary tree votes is 0.5 (at 50/50 split)
        dispersion_uncertainty = min(1.0, tree_std / 0.40)
        
    # Composite weighted uncertainty
    u = 0.60 * boundary_uncertainty + 0.25 * calib_uncertainty + 0.15 * dispersion_uncertainty
    return round(float(max(0.0, min(1.0, u))), 4)


def evaluate_confidence_tier(
    fraud_prob: float,
    block_threshold: float = 0.34,
    calibrated_prob: Optional[float] = None,
    tree_std: Optional[float] = None,
    boundary_ambiguity_band: float = 0.05,
    high_confidence_distance: float = 0.12,
    calibration_divergence_max: float = 0.15
) -> Tuple[ConfidenceTier, float]:
    """
    Evaluate the epistemic and aleatoric confidence of the model prediction.
    
    Rules:
    - LOW_CONFIDENCE: Prediction lies within the critical ambiguity band around decision threshold,
      or shows severe calibration discrepancy (> 0.15) or high tree variance.
    - HIGH_CONFIDENCE: Prediction is securely far from the boundary with tight calibration agreement.
    - MEDIUM_CONFIDENCE: All intermediate cases.
    """
    p = max(0.0, min(1.0, fraud_prob))
    dist_to_boundary = abs(p - block_threshold)
    
    uncertainty_score = compute_uncertainty_score(
        p, calibrated_prob=calibrated_prob, tree_std=tree_std, block_threshold=block_threshold
    )
    
    # Check for low-confidence triggers
    if dist_to_boundary <= boundary_ambiguity_band:
        return ConfidenceTier.LOW_CONFIDENCE, uncertainty_score
        
    if calibrated_prob is not None:
        if abs(p - calibrated_prob) >= calibration_divergence_max:
            return ConfidenceTier.LOW_CONFIDENCE, uncertainty_score
            
    if tree_std is not None and tree_std >= 0.38:
        return ConfidenceTier.LOW_CONFIDENCE, uncertainty_score

    # Check for high-confidence triggers
    if dist_to_boundary >= high_confidence_distance:
        if calibrated_prob is None or abs(p - calibrated_prob) < 0.08:
            return ConfidenceTier.HIGH_CONFIDENCE, uncertainty_score

    return ConfidenceTier.MEDIUM_CONFIDENCE, uncertainty_score
