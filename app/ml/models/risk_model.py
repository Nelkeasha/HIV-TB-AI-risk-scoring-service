"""
RandomForestClassifier for patient risk scoring.

Classes: LOW(0)=0-40, MODERATE(1)=41-69, HIGH(2)=70-84, CRITICAL(3)=85-100
Output : risk_score (0-100) and risk_level string.

On first use, trains on synthetic data and saves risk_model.pkl + scaler.pkl.
Subsequent uses load from disk.
"""

import os
import logging
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_DIR   = Path(__file__).parent.parent / "trained"
MODEL_PATH  = MODEL_DIR / "risk_model.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"

LABEL_MAP = {0: "LOW", 1: "MODERATE", 2: "HIGH", 3: "CRITICAL"}
SCORE_MAP = {0: 20.0, 1: 55.0, 2: 77.0, 3: 92.0}

_model:  RandomForestClassifier | None = None
_scaler: StandardScaler | None = None


def _generate_training_data(n=1200):
    rng = np.random.default_rng(42)

    def make_class(n, adh_range, resp_range, se_range, mv_range, label):
        adh7  = rng.uniform(*adh_range, n)
        adh14 = np.clip(adh7  + rng.normal(0, 0.05, n), 0, 1)
        adh30 = np.clip(adh14 + rng.normal(0, 0.05, n), 0, 1)
        resp  = rng.uniform(*resp_range, n)
        se    = rng.integers(*se_range, n)
        mv    = rng.integers(*mv_range, n)
        return np.column_stack([adh7, adh14, adh30, resp, se, mv]), np.full(n, label)

    X0, y0 = make_class(n, (0.85, 1.00), (60, 180),  (0, 1), (0, 1), 0)
    X1, y1 = make_class(n, (0.65, 0.85), (45, 120),  (0, 2), (0, 2), 1)
    X2, y2 = make_class(n, (0.40, 0.65), (20, 60),   (1, 3), (1, 3), 2)
    X3, y3 = make_class(n, (0.00, 0.40), (5,  30),   (2, 5), (2, 5), 3)

    X = np.vstack([X0, X1, X2, X3])
    y = np.concatenate([y0, y1, y2, y3])
    return X, y


def _train():
    logger.info("Training risk model on synthetic data...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    X, y = _generate_training_data()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
    model.fit(X_scaled, y)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    logger.info("Risk model trained and saved to %s", MODEL_DIR)
    return model, scaler


def load():
    global _model, _scaler
    if _model is not None:
        return
    if MODEL_PATH.exists() and SCALER_PATH.exists():
        _model  = joblib.load(MODEL_PATH)
        _scaler = joblib.load(SCALER_PATH)
        logger.info("Risk model loaded from disk")
    else:
        _model, _scaler = _train()


def predict(features: dict) -> tuple[float, str]:
    """Returns (risk_score 0-100, risk_level string)."""
    load()
    X = np.array([[
        features["adherence_7d"],
        features["adherence_14d"],
        features["adherence_30d"],
        features["avg_response_time_seconds"],
        features["side_effect_reports_14d"],
        features["missed_visits_30d"],
    ]])
    X_scaled = _scaler.transform(X)
    label_idx  = int(_model.predict(X_scaled)[0])
    proba      = _model.predict_proba(X_scaled)[0]

    # Base score from class bucket + continuous refinement from probabilities
    base  = SCORE_MAP[label_idx]
    boost = float(proba[min(label_idx + 1, 3)]) * 10 - float(proba[max(label_idx - 1, 0)]) * 5
    score = round(min(max(base + boost, 0.0), 100.0), 2)

    return score, LABEL_MAP[label_idx]
