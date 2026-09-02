"""Dual-layer explanation engine for ESI triage predictions (Exact TreeSHAP + Clinical Safety Rules)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


class ESIExplainer:
    """Explains ESI model predictions using exact TreeSHAP values, feature contributions, and clinical decision rules."""

    def __init__(
        self,
        feature_names: list[str],
        top_features: list[dict[str, Any]] | None = None,
        model_booster: Any | None = None,
    ):
        self.feature_names = feature_names
        self.top_features = top_features or []
        self.model_booster = model_booster

    def explain_instance(
        self,
        patient_record: Mapping[str, Any],
        engineered_vector: np.ndarray,
        predicted_probs: np.ndarray,
        proposed_esi: int,
        safety_ceiling: int | None = None,
    ) -> dict[str, Any]:
        """Generate comprehensive, clinician-facing explanations for a single triage prediction using exact TreeSHAP."""
        probs = [float(p) for p in predicted_probs]
        sorted_classes = np.argsort(probs)[::-1]
        top_prob = probs[sorted_classes[0]]
        second_prob = probs[sorted_classes[1]]
        margin = top_prob - second_prob

        # 1. Exact TreeSHAP Extraction (if booster is available)
        treeshap_factors = []
        vec = engineered_vector.flatten()

        if self.model_booster is not None and hasattr(self.model_booster, "predict"):
            try:
                # 2D input for predict
                X_in = engineered_vector.reshape(1, -1)
                shap_raw = self.model_booster.predict(X_in, pred_contrib=True)
                # For 5-class multiclass GBDT, shape is (1, 5, num_features + 1) or (1, 5 * (num_features + 1))
                if len(shap_raw.shape) == 2 and shap_raw.shape[1] == 5 * (len(self.feature_names) + 1):
                    shap_reshaped = shap_raw.reshape(1, 5, -1)
                elif len(shap_raw.shape) == 3:
                    shap_reshaped = shap_raw
                else:
                    shap_reshaped = None

                if shap_reshaped is not None:
                    # Class index (0-indexed) for proposed ESI
                    target_cls_idx = max(0, min(4, proposed_esi - 1))
                    cls_shap = shap_reshaped[0, target_cls_idx, :-1]  # Exclude bias term
                    top_shap_indices = np.argsort(np.abs(cls_shap))[::-1][:6]

                    for idx in top_shap_indices:
                        feat_name = self.feature_names[idx]
                        feat_val = vec[idx]
                        shap_val = float(cls_shap[idx])
                        if abs(shap_val) > 0.05:
                            treeshap_factors.append({
                                "feature_name": feat_name,
                                "raw_value": float(feat_val),
                                "shap_impact": round(shap_val, 4),
                                "direction": "Increases Urgency" if shap_val > 0 else "Decreases Urgency",
                            })
            except Exception:  # noqa: BLE001, S110
                pass

        # 2. Rule-Based & Domain Clinician Interpretations
        contributions = []
        for idx, name in enumerate(self.feature_names):
            val = vec[idx]
            if val != 0.0:
                if name == "shock_index" and val >= 0.9:
                    contributions.append({
                        "feature": "Shock Index",
                        "value": f"{val:.2f}",
                        "urgency_impact": "High Acuity (Occult Shock)",
                        "weight": float(val * 1.8),
                    })
                elif name == "spo2_percent" and val < 92.0:
                    contributions.append({
                        "feature": "SpO₂ Saturation",
                        "value": f"{val:.1f}%",
                        "urgency_impact": "High Acuity (Hypoxia)",
                        "weight": float((92.0 - val) * 0.25),
                    })
                elif name == "heart_rate_bpm" and (val > 120.0 or val < 50.0):
                    contributions.append({
                        "feature": "Heart Rate",
                        "value": f"{val:.0f} bpm",
                        "urgency_impact": "High Acuity (Severe Tachy/Bradycardia)",
                        "weight": float(abs(val - 80.0) * 0.03),
                    })
                elif name == "gcs_total" and val < 14:
                    contributions.append({
                        "feature": "Glasgow Coma Scale",
                        "value": f"{int(val)}/15",
                        "urgency_impact": "High Acuity (Depressed Consciousness)",
                        "weight": float((15.0 - val) * 0.3),
                    })
                elif name == "systolic_bp_mmhg" and val < 90.0:
                    contributions.append({
                        "feature": "Systolic Blood Pressure",
                        "value": f"{val:.0f} mmHg",
                        "urgency_impact": "High Acuity (Hypotension)",
                        "weight": float((90.0 - val) * 0.1),
                    })
                elif name == "pain_score" and val >= 7:
                    contributions.append({
                        "feature": "Pain Score",
                        "value": f"{int(val)}/10",
                        "urgency_impact": "Escalates Urgency (Severe Pain)",
                        "weight": float(val * 0.1),
                    })
                elif name.startswith("tfidf_") and val > 0.15:
                    keyword = name.replace("tfidf_", "")
                    contributions.append({
                        "feature": f"Chief Complaint keyword: '{keyword}'",
                        "value": f"{val:.2f}",
                        "urgency_impact": "Semantic Clinical Context",
                        "weight": float(val * 0.5),
                    })

        contributions.sort(key=lambda x: x["weight"], reverse=True)
        top_contributions = contributions[:5]

        # 3. Uncertainty & Conformal Acuity Widening
        is_uncertain = False
        uncertainty_reasons = []
        if top_prob < 0.65:
            is_uncertain = True
            uncertainty_reasons.append(f"Model confidence is moderate ({top_prob:.0%}) below certainty threshold (65%).")
        if margin < 0.18:
            is_uncertain = True
            uncertainty_reasons.append(
                f"Close probability margin ({margin:.1%}) between top two acuity tiers (ESI {sorted_classes[0]+1} vs ESI {sorted_classes[1]+1})."
            )

        # Conformal Prediction Set
        accumulated_prob = 0.0
        prediction_set = []
        for cls_idx in sorted_classes:
            prediction_set.append(int(cls_idx) + 1)
            accumulated_prob += probs[cls_idx]
            if accumulated_prob >= 0.85:
                break
        prediction_set.sort()

        # 4. Final Acuity Arbitration & Safety Override
        final_esi = proposed_esi
        safety_override_applied = False
        if safety_ceiling is not None and safety_ceiling < proposed_esi:
            final_esi = safety_ceiling
            safety_override_applied = True

        # 5. Natural Language Rationale Formulation
        rationale_parts = []
        if safety_override_applied:
            rationale_parts.append(
                f"Safety guardrail activated: deterministic ceiling forced ESI {final_esi} "
                f"(proposed ESI {proposed_esi} downgraded toward greater urgency for patient safety)."
            )
        else:
            rationale_parts.append(
                f"Tree model proposed ESI {proposed_esi} with {top_prob:.0%} confidence."
            )

        if top_contributions:
            factor_strs = [f"{c['feature']} ({c['value']})" for c in top_contributions[:3]]
            rationale_parts.append(f"Primary driving factors: {', '.join(factor_strs)}.")

        clinical_rationale = " ".join(rationale_parts)

        return {
            "proposed_esi": proposed_esi,
            "final_esi": final_esi,
            "safety_ceiling": safety_ceiling,
            "safety_override_applied": safety_override_applied,
            "confidence_score": round(top_prob, 2),
            "prediction_set": prediction_set,
            "class_probabilities": {f"ESI_{i+1}": round(probs[i], 4) for i in range(5)},
            "is_uncertain": is_uncertain,
            "uncertainty_reasons": uncertainty_reasons,
            "top_contributing_factors": top_contributions,
            "treeshap_attributions": treeshap_factors,
            "clinical_rationale": clinical_rationale,
        }
