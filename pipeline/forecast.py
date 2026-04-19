"""Time-series forecasting of average tone per country.

Uses a scikit-learn gradient-boosted regressor with lagged features to
forecast the next-hour AvgTone per country. Evaluated with MAE/RMSE on a
held-out temporal split (no leakage from the future into the past).
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from config import MODELS_DIR
from pipeline.mlops import log_run

MODEL = MODELS_DIR / "tone_forecaster.pkl"
META = MODELS_DIR / "tone_forecaster_meta.json"

LAGS = [1, 2, 3, 6, 12]


def _featurize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["CountryName", "Hour"]).copy()
    for lag in LAGS:
        df[f"tone_lag_{lag}"] = df.groupby("CountryName")["AvgTone"].shift(lag)
    df["tone_rolling_3"] = (
        df.groupby("CountryName")["AvgTone"].shift(1)
          .rolling(3, min_periods=1).mean().reset_index(0, drop=True)
    )
    df["hour_of_day"] = df["Hour"].dt.hour
    df["day_of_week"] = df["Hour"].dt.dayofweek
    return df.dropna()


def _aggregate_hourly(pdf: pd.DataFrame) -> pd.DataFrame:
    pdf = pdf.copy()
    pdf["Hour"] = pd.to_datetime(pdf["DateFormatted"]).dt.floor("h")
    grouped = (
        pdf.groupby(["CountryName", "Hour"])
           .agg(AvgTone=("AvgTone", "mean"),
                EventCount=("GoldsteinScale", "size"))
           .reset_index()
    )
    return grouped


def train(pdf: pd.DataFrame) -> dict:
    hourly = _aggregate_hourly(pdf)
    # Keep only countries with enough history
    counts = hourly.groupby("CountryName").size()
    keep = counts[counts >= 15].index
    hourly = hourly[hourly["CountryName"].isin(keep)]

    if hourly.empty:
        print("[forecast] not enough history for any country — skipping")
        return {"skipped": True}

    feats = _featurize(hourly)
    feature_cols = [f"tone_lag_{l}" for l in LAGS] + [
        "tone_rolling_3", "hour_of_day", "day_of_week", "EventCount"
    ]
    # Temporal split: last 20% of hours as test
    cutoff = feats["Hour"].quantile(0.8)
    train_df = feats[feats["Hour"] <= cutoff]
    test_df = feats[feats["Hour"] > cutoff]
    if test_df.empty:
        test_df = train_df.tail(max(10, len(train_df) // 10))
        train_df = train_df.iloc[: len(train_df) - len(test_df)]

    X_train = train_df[feature_cols].to_numpy()
    y_train = train_df["AvgTone"].to_numpy()
    X_test = test_df[feature_cols].to_numpy()
    y_test = test_df["AvgTone"].to_numpy()

    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    mae = float(mean_absolute_error(y_test, pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    metrics = {
        "mae": mae,
        "rmse": rmse,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "countries": int(hourly["CountryName"].nunique()),
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_cols": feature_cols}, MODEL)
    META.write_text(json.dumps(metrics, indent=2))
    log_run(
        model_name="gbr_tone_forecaster",
        params={"n_estimators": 200, "max_depth": 4, "lr": 0.05, "lags": LAGS},
        metrics=metrics,
        stage="production",
    )
    print(f"[forecast] trained: mae={mae:.3f} rmse={rmse:.3f} "
          f"countries={metrics['countries']}")
    return metrics


def load() -> dict | None:
    if not MODEL.exists():
        return None
    return joblib.load(MODEL)
