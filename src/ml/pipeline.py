"""End-to-end inference and explanation pipeline for ResiliCare ESI Triage."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .explainer import ESIExplainer
from .feature_engineering import ESIFeatureEngineer

DEFAULT_ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "esi_lgbm_model.joblib"
FALLBACK_ARTIFACT_PATH = Path("ESI_classification_model/artifacts/esi_lgbm_model.joblib")


class ESITriagePipeline:
    """Production triage pipeline integrating ML scoring, safety rules, and explanations."""

    def __init__(self, artifact_path: str | Path | None = None):
        if artifact_path is not None:
            self.artifact_path = Path(artifact_path)
        elif DEFAULT_ARTIFACT_PATH.exists():
            self.artifact_path = DEFAULT_ARTIFACT_PATH
        else:
            self.artifact_path = FALLBACK_ARTIFACT_PATH

        self.model = None
        self.engineer: ESIFeatureEngineer | None = None
        self.feature_names: list[str] = []
        self.explainer: ESIExplainer | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Load serialized model artifact bundle."""
        if not self.artifact_path.exists():
            raise FileNotFoundError(
                f"ESI ML model artifact not found at {self.artifact_path}. "
                "Ensure artifacts are placed in src/ml/artifacts/ or ESI_classification_model/artifacts/."
            )

        bundle = joblib.load(self.artifact_path)
        self.model = bundle["model"]
        self.engineer = bundle["engineer"]
        self.feature_names = bundle.get("feature_names", getattr(self.engineer, "feature_names", []))
        booster = getattr(self.model, "booster_", None)
        self.explainer = ESIExplainer(self.feature_names, bundle.get("top_features", []), model_booster=booster)

    def predict_encounter(
        self,
        encounter_data: Mapping[str, Any],
        safety_ceiling: int | None = None,
    ) -> dict[str, Any]:
        """Predict ESI level, class probabilities, uncertainty set, and clinical explanations."""
        if self.engineer is None or self.model is None or self.explainer is None:
            raise RuntimeError("ESITriagePipeline is not properly loaded")

        # Normalize alias keys from FastAPI schemas and services
        norm_data = dict(encounter_data)
        if "age_years" in norm_data and "age" not in norm_data:
            norm_data["age"] = norm_data["age_years"]
        if "estimated_age_years" in norm_data and "age" not in norm_data:
            norm_data["age"] = norm_data["estimated_age_years"]
        if "sex_at_birth" in norm_data and "sex" not in norm_data:
            norm_data["sex"] = norm_data["sex_at_birth"]
        if "hr_bpm" in norm_data and "heart_rate_bpm" not in norm_data:
            norm_data["heart_rate_bpm"] = norm_data["hr_bpm"]
        if "rr_bpm" in norm_data and "respiratory_rate_bpm" not in norm_data:
            norm_data["respiratory_rate_bpm"] = norm_data["rr_bpm"]
        if "spo2_pct" in norm_data and "spo2_percent" not in norm_data:
            norm_data["spo2_percent"] = norm_data["spo2_pct"]
        if "sbp_mmhg" in norm_data and "systolic_bp_mmhg" not in norm_data:
            norm_data["systolic_bp_mmhg"] = norm_data["sbp_mmhg"]
        if "dbp_mmhg" in norm_data and "diastolic_bp_mmhg" not in norm_data:
            norm_data["diastolic_bp_mmhg"] = norm_data["dbp_mmhg"]
        if "temp_c" in norm_data and "temperature_c" not in norm_data:
            norm_data["temperature_c"] = norm_data["temp_c"]

        # Compute GCS total if components provided
        if ("gcs_total" not in norm_data or norm_data["gcs_total"] is None) and all(
            norm_data.get(k) is not None for k in ["gcs_eye", "gcs_verbal", "gcs_motor"]
        ):
            norm_data["gcs_total"] = int(norm_data["gcs_eye"]) + int(norm_data["gcs_verbal"]) + int(norm_data["gcs_motor"])

        # Convert dictionary to 1-row DataFrame
        df = pd.DataFrame([norm_data])

        # Feature transform
        X = self.engineer.transform(df)

        # Multi-class probability prediction
        probs = self.model.predict_proba(X)[0]
        proposed_esi = int(np.argmax(probs)) + 1

        # Generate dual explanation and apply safety guardrail
        explanation = self.explainer.explain_instance(
            patient_record=encounter_data,
            engineered_vector=X[0],
            predicted_probs=probs,
            proposed_esi=proposed_esi,
            safety_ceiling=safety_ceiling,
        )

        return {
            "encounter_id": str(encounter_data.get("encounter_id", "ENC-UNSPECIFIED")),
            "proposed_esi": proposed_esi,
            "final_esi": explanation["final_esi"],
            "safety_ceiling": safety_ceiling,
            "safety_override_applied": explanation["safety_override_applied"],
            "confidence_score": explanation["confidence_score"],
            "prediction_set": explanation["prediction_set"],
            "class_probabilities": explanation["class_probabilities"],
            "is_uncertain": explanation["is_uncertain"],
            "uncertainty_reasons": explanation["uncertainty_reasons"],
            "top_contributing_factors": explanation["top_contributing_factors"],
            "treeshap_attributions": explanation.get("treeshap_attributions", []),
            "clinical_rationale": explanation["clinical_rationale"],
        }
