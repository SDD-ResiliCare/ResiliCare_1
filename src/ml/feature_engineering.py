"""Clinical feature engineering for ESI triage acuity prediction."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


class ESIFeatureEngineer:
    """Transforms raw clinical encounter data into ML-ready tabular and text features."""

    def __init__(self, max_tfidf_features: int = 100):
        self.max_tfidf_features = max_tfidf_features
        self.tfidf = TfidfVectorizer(
            max_features=max_tfidf_features,
            ngram_range=(1, 2),
            stop_words="english",
            token_pattern=r"(?u)\b\w+\b",
        )
        self.is_fitted = False
        self.feature_names: list[str] = []

        # Population median defaults for missing vital imputation
        self.vital_medians = {
            "heart_rate_bpm": 80.0,
            "respiratory_rate_bpm": 16.0,
            "spo2_percent": 98.0,
            "systolic_bp_mmhg": 120.0,
            "diastolic_bp_mmhg": 80.0,
            "temperature_c": 36.8,
            "pain_score": 0.0,
            "gcs_total": 15.0,
        }

    def _get_series(self, df: pd.DataFrame, col: str, default: Any = np.nan) -> pd.Series:
        if col in df.columns:
            return df[col]
        return pd.Series(default, index=df.index)

    def _compute_clinical_composites(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute shock index, MAP, pulse pressure, qSOFA, and SIRS proxies."""
        feat = pd.DataFrame(index=df.index)

        hr_raw = self._get_series(df, "heart_rate_bpm")
        rr_raw = self._get_series(df, "respiratory_rate_bpm")
        spo2_raw = self._get_series(df, "spo2_percent")
        sbp_raw = self._get_series(df, "systolic_bp_mmhg")
        dbp_raw = self._get_series(df, "diastolic_bp_mmhg")
        temp_raw = self._get_series(df, "temperature_c")
        pain_raw = self._get_series(df, "pain_score", default=0.0)
        gcs_raw = self._get_series(df, "gcs_total", default=15.0)
        age_raw = self._get_series(df, "age", default=45.0)

        hr = pd.to_numeric(hr_raw, errors="coerce").fillna(self.vital_medians["heart_rate_bpm"]).astype(float)
        rr = pd.to_numeric(rr_raw, errors="coerce").fillna(self.vital_medians["respiratory_rate_bpm"]).astype(float)
        spo2 = pd.to_numeric(spo2_raw, errors="coerce").fillna(self.vital_medians["spo2_percent"]).astype(float)
        sbp = pd.to_numeric(sbp_raw, errors="coerce").fillna(self.vital_medians["systolic_bp_mmhg"]).astype(float)
        dbp = pd.to_numeric(dbp_raw, errors="coerce").fillna(self.vital_medians["diastolic_bp_mmhg"]).astype(float)
        temp = pd.to_numeric(temp_raw, errors="coerce").fillna(self.vital_medians["temperature_c"]).astype(float)
        pain = pd.to_numeric(pain_raw, errors="coerce").fillna(self.vital_medians["pain_score"]).astype(float)
        gcs = pd.to_numeric(gcs_raw, errors="coerce").fillna(self.vital_medians["gcs_total"]).astype(float)
        age = pd.to_numeric(age_raw, errors="coerce").fillna(45.0).astype(float)

        # 1. Shock Index = HR / SBP
        safe_sbp = sbp.replace(0, 1.0)
        feat["shock_index"] = hr / safe_sbp
        feat["shock_index_elevated"] = (feat["shock_index"] >= 0.9).astype(float)

        # 2. Mean Arterial Pressure (MAP) = (2 * DBP + SBP) / 3
        feat["mean_arterial_pressure"] = (2.0 * dbp + sbp) / 3.0
        feat["map_hypoperfusion"] = (feat["mean_arterial_pressure"] < 65.0).astype(float)

        # 3. Pulse Pressure = SBP - DBP
        feat["pulse_pressure"] = sbp - dbp

        # 4. Proxy qSOFA criteria
        qsofa_rr = (rr >= 22.0).astype(float)
        qsofa_sbp = (sbp <= 100.0).astype(float)
        qsofa_gcs = (gcs < 15.0).astype(float)
        feat["qsofa_score"] = qsofa_rr + qsofa_sbp + qsofa_gcs
        feat["qsofa_high_risk"] = (feat["qsofa_score"] >= 2.0).astype(float)

        # 5. SIRS criteria
        sirs_temp = ((temp > 38.0) | (temp < 36.0)).astype(float)
        sirs_hr = (hr > 90.0).astype(float)
        sirs_rr = (rr > 20.0).astype(float)
        feat["sirs_score"] = sirs_temp + sirs_hr + sirs_rr
        feat["sirs_high_risk"] = (feat["sirs_score"] >= 2.0).astype(float)

        # 6. Physiological Extremes
        feat["severe_hypoxia"] = (spo2 < 92.0).astype(float)
        feat["severe_tachycardia"] = (hr > 130.0).astype(float)
        feat["severe_bradycardia"] = (hr < 50.0).astype(float)
        feat["severe_hypotension"] = (sbp < 80.0).astype(float)
        feat["severe_pain"] = (pain >= 7.0).astype(float)
        feat["gcs_comatose"] = (gcs <= 8.0).astype(float)

        # 7. Age vulnerabilities
        feat["age"] = age
        feat["is_elderly"] = (age >= 65.0).astype(float)
        feat["is_pediatric"] = (age < 18.0).astype(float)

        # 8. Missingness indicators
        feat["missing_hr"] = pd.to_numeric(hr_raw, errors="coerce").isna().astype(float)
        feat["missing_rr"] = pd.to_numeric(rr_raw, errors="coerce").isna().astype(float)
        feat["missing_spo2"] = pd.to_numeric(spo2_raw, errors="coerce").isna().astype(float)
        feat["missing_sbp"] = pd.to_numeric(sbp_raw, errors="coerce").isna().astype(float)
        feat["missing_temp"] = pd.to_numeric(temp_raw, errors="coerce").isna().astype(float)
        feat["total_missing_vitals"] = (
            feat["missing_hr"] + feat["missing_rr"] + feat["missing_spo2"] + feat["missing_sbp"] + feat["missing_temp"]
        )

        # 9. Imputed raw vitals
        feat["heart_rate_bpm"] = hr
        feat["respiratory_rate_bpm"] = rr
        feat["spo2_percent"] = spo2
        feat["systolic_bp_mmhg"] = sbp
        feat["diastolic_bp_mmhg"] = dbp
        feat["temperature_c"] = temp
        feat["pain_score"] = pain
        feat["gcs_total"] = gcs

        # 10. AVPU encoding
        avpu_map = {"A": 0.0, "V": 1.0, "P": 2.0, "U": 3.0}
        avpu_series = self._get_series(df, "avpu", default="A")
        feat["avpu_level"] = avpu_series.fillna("A").map(lambda x: avpu_map.get(str(x).upper(), 0.0)).astype(float)

        # 11. Arrival Mode & Sex
        arr_series = self._get_series(df, "arrival_mode", default="")
        sex_series = self._get_series(df, "sex", default="")
        comorb_series = self._get_series(df, "num_comorbidities", default=0.0)

        feat["arrival_ambulance"] = (arr_series.fillna("").astype(str).str.lower() == "ambulance").astype(float)
        feat["arrival_walkin"] = (arr_series.fillna("").astype(str).str.lower() == "walk-in").astype(float)
        feat["sex_male"] = (sex_series.fillna("").astype(str).str.lower() == "male").astype(float)
        feat["num_comorbidities"] = pd.to_numeric(comorb_series, errors="coerce").fillna(0.0).astype(float)

        return feat

    def fit_transform(self, df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
        """Fit TF-IDF on text and transform full tabular + text dataset."""
        cc = df["chief_complaint"] if "chief_complaint" in df else pd.Series("", index=df.index)
        pd_det = df["presenting_details"] if "presenting_details" in df else pd.Series("", index=df.index)
        text_data = (cc.fillna("") + " " + pd_det.fillna("")).astype(str)
        tfidf_matrix = self.tfidf.fit_transform(text_data).toarray()
        tfidf_feature_names = [f"tfidf_{w}" for w in self.tfidf.get_feature_names_out()]

        composites_df = self._compute_clinical_composites(df)
        tabular_matrix = composites_df.to_numpy()
        tabular_feature_names = list(composites_df.columns)

        X = np.hstack([tabular_matrix, tfidf_matrix])
        self.feature_names = tabular_feature_names + tfidf_feature_names
        self.is_fitted = True
        return X, self.feature_names

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Transform test/production dataset using fitted vectorizer."""
        if not self.is_fitted:
            raise RuntimeError("ESIFeatureEngineer must be fitted or loaded before transform()")

        cc = df["chief_complaint"] if "chief_complaint" in df else pd.Series("", index=df.index)
        pd_det = df["presenting_details"] if "presenting_details" in df else pd.Series("", index=df.index)
        text_data = (cc.fillna("") + " " + pd_det.fillna("")).astype(str)
        tfidf_matrix = self.tfidf.transform(text_data).toarray()

        composites_df = self._compute_clinical_composites(df)
        tabular_matrix = composites_df.to_numpy()

        return np.hstack([tabular_matrix, tfidf_matrix])
