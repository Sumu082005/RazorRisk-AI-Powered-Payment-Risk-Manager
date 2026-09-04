# RazorRisk — Deterministic Risk Decision Engine Specification

**Project:** RazorRisk (Razorpay AI Buildathon 2026 — AI Risk Manager Track)  
**Layer:** Decisioning & Policy Engine Layer  
**Engine Version:** `1.0.0`  
**Policy Version:** `2026.08-v1`  
**Status:** Implemented, Tested (`13/13 unit tests passing`), and Verified

---

## 1. System Architecture & Core Principle

RazorRisk decouples probabilistic machine learning risk scoring from deterministic business decisioning:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RAZORRISK RISK PIPELINE                         │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                         ┌────────────────────┐
                         │   RAW ML MODEL     │  "How likely is this transaction
                         │ (Random Forest 100)│   to be fraudulent?"
                         └─────────┬──────────┘
                                   │ Raw Probability P(y=1)
                                   ▼
                         ┌────────────────────┐
                         │ PROBABILITY CALIB  │  Isotonic / Platt Calibration
                         │ & TREE DISPERSION  │  Estimator variance & delta
                         └─────────┬──────────┘
                                   │ Calibrated P + Tree Std
                                   ▼
                         ┌────────────────────┐
                         │ UNCERTAINTY & CONF │  HIGH / MEDIUM / LOW CONFIDENCE
                         │ TIERING SUBSYSTEM  │  Distance-to-boundary metrics
                         └─────────┬──────────┘
                                   │ Structured Model Evidence
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│               DETERMINISTIC POLICY ENGINE (100% Python Code)           │
│                                                                        │
│  [Merchant Risk Posture]  [Safety Gates]  [Asymmetric Loss Evaluation] │
│  FRAUD_PREVENTION         Fail-Closed     E[Loss | Action]             │
│  BALANCED                 Zero-Amt Probe                               │
│  CUSTOMER_EXPERIENCE      $10k Gate                                    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
                         ┌────────────────────┐
                         │ OPERATIONAL ACTION │  Deterministic Decision Output
                         │  APPROVE / REVIEW  │  + Immutable Structured Audit Trail
                         │      / BLOCK       │
                         └─────────┬──────────┘
                                   │
                                   ▼
                         ┌────────────────────┐
                         │  ANALYST COPILOT   │  "How do we explain that decision
                         │  (Read-Only LLM)   │   to a human risk analyst?"
                         └────────────────────┘
```

> [!IMPORTANT]
> **Core Architectural Security Invariant:**  
> The machine learning model produces a risk score. The deterministic policy engine produces the operational financial/security action. The downstream LLM Copilot is strictly read-only and **cannot alter, override, or mutate the operational decision**.

---

## 2. Decision Engine Contract & Data Schema

The decision engine is implemented in Python under [`razorrisk/engine/`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/razorrisk/engine).

### Input: `ModelEvidence`
```python
@dataclass
class ModelEvidence:
    transaction_id: str
    transaction_amount: float
    fraud_probability: float
    calibrated_probability: Optional[float] = None
    uncertainty: Optional[float] = None
    tree_dispersion_std: Optional[float] = None
    feature_contributions: Dict[str, float] = field(default_factory=dict)
    raw_features: Dict[str, float] = field(default_factory=dict)
    model_version: str = "RandomForest-v1.0.0"
```

### Output: `DecisionResult`
```python
@dataclass
class DecisionResult:
    decision_id: str
    transaction_id: str
    risk_score: float
    risk_tier: RiskTier                  # LOW, MEDIUM, HIGH, CRITICAL
    confidence_tier: ConfidenceTier      # HIGH_CONFIDENCE, MEDIUM_CONFIDENCE, LOW_CONFIDENCE
    recommended_action: Action           # APPROVE, REVIEW, BLOCK
    policy_id: str
    policy_version: str
    cost_profile: CostProfileName        # FRAUD_PREVENTION, BALANCED, CUSTOMER_EXPERIENCE
    triggered_rules: List[TriggeredRule]
    estimated_expected_loss: float       # In modeled currency ($)
    explanation_factors: List[Dict[str, Any]]
    requires_human_review: bool
    decision_timestamp: str
    model_version: str
    audit_event: Dict[str, Any]
```

---

## 3. Risk Tiers vs Operational Policy Thresholds

We strictly distinguish between **Model Risk Tiers** (intrinsic predicted probability ranges) and **Operational Policy Action Thresholds** (posture-dependent intervention gates):

### Model Risk Tiers (Intrinsic Probability)

| Risk Tier | Probability Range | Description | Default Action Baseline |
|-----------|-------------------|-------------|-------------------------|
| **`LOW`** | $0.00 \le P < 0.10$ | Legitimate transaction pattern | `APPROVE` |
| **`MEDIUM`** | $0.10 \le P < T_{\text{block}}$ | Elevated risk or anomalous signature | `REVIEW` |
| **`HIGH`** | $T_{\text{block}} \le P < 0.80$ | High fraud probability | `BLOCK` (if High Conf) / `REVIEW` (if Low Conf) |
| **`CRITICAL`** | $P \ge 0.80$ | Severe fraud indicator | `BLOCK` (Hard lock) |

---

## 4. Uncertainty & Confidence Tiering

Uncertainty is evaluated using boundary proximity, calibration gap, and ensemble tree dispersion ($\sigma_{\text{trees}}$):

### Formulas:
1. **Distance to Decision Boundary:**
   $$d_{\text{boundary}} = |P_{\text{raw}} - T_{\text{block}}|$$
2. **Calibration Divergence:**
   $$\Delta_{\text{calib}} = |P_{\text{raw}} - P_{\text{calibrated}}|$$
3. **Normalized Uncertainty Metric ($U \in [0, 1]$):**
   $$U = 0.60 \cdot \max\left(0, 1 - \frac{d_{\text{boundary}}}{0.30}\right) + 0.25 \cdot \min\left(1, \frac{\Delta_{\text{calib}}}{0.20}\right) + 0.15 \cdot \min\left(1, \frac{\sigma_{\text{trees}}}{0.40}\right)$$

### Confidence Tier Classification:
- **`LOW_CONFIDENCE`:** Triggered when $d_{\text{boundary}} \le 0.05$ (within ambiguity band) OR $\Delta_{\text{calib}} \ge 0.15$ OR $\sigma_{\text{trees}} \ge 0.38$.
- **`HIGH_CONFIDENCE`:** Triggered when $d_{\text{boundary}} \ge 0.12$ AND $\Delta_{\text{calib}} < 0.08$.
- **`MEDIUM_CONFIDENCE`:** All intermediate cases.

> [!NOTE]
> **Safety Invariant on Uncertainty:**  
> When a transaction falls into the `HIGH` risk tier ($T_{\text{block}} \le P < 0.80$) but receives `LOW_CONFIDENCE`, the policy engine executes Rule `SAFE-08-UNCERTAINTY-DOWNGRADE` to **downgrade automated BLOCK to human REVIEW**, protecting genuine customers from false rejections near the decision threshold.

---

## 5. Asymmetric Cost Profiles (Project Assumptions)

Payment fraud economics are asymmetric. In RazorRisk, we model three distinct merchant risk postures:

```
                                  COST PROFILE PARAMETERS
┌──────────────────────────────┬──────────────────┬──────────────┬──────────────┬──────────────┬─────────────┐
│ Cost Profile Posture         │ Review Threshold │ Block Thresh │ Review Cost  │ Chargeback   │ FP Friction │
│                              │ (T_review)       │ (T_block)    │ (C_review)   │ Fee (C_cb)   │ Cost (C_fp) │
├──────────────────────────────┼──────────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ 1. FRAUD_PREVENTION          │ 0.08             │ 0.25         │ $10.00 / txn │ $15.00 / txn │ $25.00      │
│ 2. BALANCED                  │ 0.12             │ 0.34         │ $35.00 / txn │ $15.00 / txn │ $50.00      │
│ 3. CUSTOMER_EXPERIENCE       │ 0.18             │ 0.45         │ $75.00 / txn │ $15.00 / txn │ $100.00     │
└──────────────────────────────┴──────────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
```

### Mathematical Formulation of Expected Loss:

For any candidate action $a \in \{\text{APPROVE}, \text{REVIEW}, \text{BLOCK}\}$, expected financial loss is computed as:

1. **Expected Loss given APPROVE:**
   $$\mathbb{E}[\text{Loss} \mid \text{APPROVE}] = P(\text{Fraud}) \times (\text{Amount} + C_{\text{chargeback\_fee}})$$
2. **Expected Loss given BLOCK:**
   $$\mathbb{E}[\text{Loss} \mid \text{BLOCK}] = (1 - P(\text{Fraud})) \times C_{\text{false\_positive\_friction}}$$
3. **Expected Loss given REVIEW:**
   $$\mathbb{E}[\text{Loss} \mid \text{REVIEW}] = C_{\text{review}} + P(\text{Fraud}) \times (1 - \alpha) \times (\text{Amount} + C_{\text{cb}}) + (1 - P(\text{Fraud})) \times (1 - \alpha) \times C_{\text{fp}}$$
   *(where $\alpha = 0.95$ represents human analyst review accuracy).*

*Note: Cost parameters are clearly documented project assumptions used for algorithmic loss minimization and do not represent internal Razorpay business figures.*

---

## 6. Deterministic Policy Rules & Safety Gates

| Rule ID | Rule Name | Severity | Condition | Action Impact |
|---------|-----------|----------|-----------|---------------|
| `SAFE-01-MALFORMED-PROB` | Malformed Probability | `CRITICAL` | $P = \text{NaN} \lor P = \pm\infty$ | Fail-closed to `REVIEW` |
| `SAFE-02-OUT-OF-BOUNDS-PROB` | Out-of-Bounds Probability | `CRITICAL` | $P < 0.0 \lor P > 1.0$ | Fail-closed to `REVIEW` |
| `SAFE-03-MALFORMED-AMOUNT` | Malformed Amount | `CRITICAL` | $\text{Amount} = \text{NaN} \lor \text{Amount} = \pm\infty$ | Fail-closed to `REVIEW` |
| `SAFE-04-NEGATIVE-AMOUNT` | Negative Amount | `CRITICAL` | $\text{Amount} < 0.0$ | Fail-closed to `REVIEW` |
| `SAFE-05-ZERO-AMOUNT-PROBE` | Zero-Amount Auth Probe | `MEDIUM` | $\text{Amount} = \$0.00 \land P \ge 0.05$ | Route to `REVIEW` |
| `SAFE-06-HIGH-EXPOSURE-AMOUNT` | High Financial Exposure Gate | `HIGH` | $\text{Amount} \ge \$10,000.00 \land P \ge 0.10$ | Route to `REVIEW` |
| `SAFE-07-CRITICAL-FRAUD-LOCK` | Critical Risk Hard Lock | `CRITICAL` | $P \ge 0.80$ | Hard `BLOCK` |
| `SAFE-08-UNCERTAINTY-DOWNGRADE` | Low Confidence Downgrade | `WARNING` | $P \ge T_{\text{block}} \land P < 0.80 \land \text{Conf} = \text{LOW}$ | Downgrade `BLOCK` $\rightarrow$ `REVIEW` |
| `POL-01-BLOCK-THRESHOLD` | Block Threshold Exceeded | `HIGH` | $P \ge T_{\text{block}}$ | `BLOCK` |
| `POL-02-REVIEW-THRESHOLD` | Review Threshold Exceeded | `MEDIUM` | $T_{\text{review}} \le P < T_{\text{block}}$ | `REVIEW` |
| `POL-03-LOW-RISK-APPROVE` | Low Risk Approval | `INFO` | $P < T_{\text{review}}$ | `APPROVE` |

---

## 7. Counterfactual Policy Simulation Results

Using the **Policy Simulator** on the validation partition ($N = 45,396$ transactions, 76 fraud cases):

```
                                  COUNTERFACTUAL SIMULATION SUMMARY
┌──────────────────────┬─────────────┬─────────────┬──────────────┬─────────────┬─────────────┬─────────────────┬──────────────────┬──────────────┐
│ Risk Posture         │ Review Cut  │ Block Cut   │ % Approved   │ % Reviewed  │ % Blocked   │ Fraud Caught %  │ Fraud Dollars %  │ Total Legit  │
│                      │ (T_review)  │ (T_block)   │              │             │             │ (Count Interc.) │ (Dollars Interc.)│ Impacted (FP)│
├──────────────────────┼─────────────┼─────────────┼──────────────┼─────────────┼─────────────┼─────────────────┼──────────────────┼──────────────┤
│ FRAUD_PREVENTION     │ 0.08        │ 0.25        │ 99.8039%     │ 0.0859%     │ 0.1101%     │ 86.84% (66/76)  │ 77.31%           │ 23 reviewed  │
│ BALANCED             │ 0.12        │ 0.34        │ 99.8172%     │ 0.0727%     │ 0.1101%     │ 86.84% (66/76)  │ 77.31%           │ 17 reviewed  │
│ CUSTOMER_EXPERIENCE  │ 0.18        │ 0.45        │ 99.8304%     │ 0.0595%     │ 0.1101%     │ 86.84% (66/76)  │ 77.31%           │ 11 reviewed  │
└──────────────────────┴─────────────┴─────────────┴──────────────┴─────────────┴─────────────┴─────────────────┴──────────────────┴──────────────┘
```

### Insights:
- Changing risk posture from `FRAUD_PREVENTION` to `CUSTOMER_EXPERIENCE` reduces legitimate transaction review friction by **52.17%** (from 23 reviews to 11 reviews) while maintaining identical high-confidence critical fraud blocking (50 fraud cases hard blocked).

---

## 8. Structured Audit Trail Event Format

Every decision produces an immutable, machine-readable JSON record containing full operational lineage:

```json
{
  "audit_event_id": "evt_a84c901e45f2",
  "decision_id": "dec_b93d01248a1c",
  "transaction_id": "tx_2026_08_94812",
  "policy_id": "POL-RAZORPAY-RISK-2026",
  "policy_version": "2026.08-v1",
  "model_version": "RandomForest-v1.0.0",
  "risk_score": 0.6542,
  "risk_tier": "HIGH",
  "confidence_tier": "HIGH_CONFIDENCE",
  "uncertainty_score": 0.1450,
  "cost_profile": "BALANCED",
  "recommended_action": "BLOCK",
  "estimated_expected_loss": 17.29,
  "triggered_rules": [
    {
      "rule_id": "POL-01-BLOCK-THRESHOLD",
      "rule_name": "Cost Profile Block Threshold Exceeded",
      "severity": "HIGH",
      "description": "Fraud probability (0.6542) meets or exceeds BALANCED block threshold (0.34)."
    }
  ],
  "execution_status": "SUCCESS",
  "decision_timestamp": "2026-08-26T22:20:45.123456+00:00"
}
```

---

## 9. Test Suite Verification & Security Proofs

The test suite in [`tests/test_decision_engine.py`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/tests/test_decision_engine.py) covers 13 test cases executed via `pytest`:

```
tests/test_decision_engine.py::TestRiskDecisionEngine::test_low_risk_high_confidence_approval PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_medium_risk_routes_to_review PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_high_risk_high_confidence_blocks PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_high_risk_low_confidence_downgrades_to_review PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_critical_risk_hard_blocks_regardless_of_dispersion PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_zero_amount_probe_handling PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_high_exposure_amount_gate PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_cost_profile_threshold_adaptation PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_boundary_safety_nan_probability PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_boundary_safety_infinite_probability PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_boundary_safety_negative_amount PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_deterministic_idempotency PASSED
tests/test_decision_engine.py::TestRiskDecisionEngine::test_llm_cannot_override_policy_decision PASSED

============================= 13 passed in 0.49s =============================
```

---

## 10. Summary of Assumptions & Operational Limitations

1. **Cost Parameter Assumptions:** Review costs ($10–$75) and friction costs ($25–$100) are explicit project simulation models designed to demonstrate algorithmic loss optimization.
2. **Review Accuracy Model:** Analyst review accuracy is modeled at 90–95% efficiency.
3. **Immutability Invariant:** Policy rules and threshold gates execute synchronously before any natural language generation occurs.
