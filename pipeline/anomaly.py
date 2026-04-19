"""Anomaly detection for regional sentiment spikes.

Combines two complementary models:

  * KMeans (Spark MLlib) — clusters events in feature space; the smallest
    cluster defines an unsupervised "anomaly cluster".
  * IsolationForest (scikit-learn) — scores each row's outlier likelihood;
    the top ``contamination`` fraction is flagged as anomalous.

A weak label is derived from the tails of AvgTone + GoldsteinScale so we
can report precision/recall against a proxy ground truth — exactly what
the proposal's evaluation plan asked for.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from pyspark.ml.clustering import KMeans
from pyspark.ml.feature import VectorAssembler
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support
from sklearn.preprocessing import StandardScaler

from config import FEATURE_COLS, MODELS_DIR
from pipeline.mlops import log_run

ISO_MODEL = MODELS_DIR / "isoforest.pkl"
ISO_SCALER = MODELS_DIR / "isoforest_scaler.pkl"


def _weak_label(pdf: pd.DataFrame) -> np.ndarray:
    """Proxy ground truth: events whose tone or Goldstein is in the far tails."""
    tone_z = (pdf["AvgTone"] - pdf["AvgTone"].mean()) / (pdf["AvgTone"].std() or 1)
    gold_z = (pdf["GoldsteinScale"] - pdf["GoldsteinScale"].mean()) / (pdf["GoldsteinScale"].std() or 1)
    return ((tone_z.abs() > 2.0) | (gold_z.abs() > 2.0)).astype(int).to_numpy()


def kmeans_cluster(df: DataFrame, k: int = 5) -> DataFrame:
    assembler = VectorAssembler(
        inputCols=FEATURE_COLS, outputCol="features", handleInvalid="skip"
    )
    assembled = assembler.transform(df)
    kmeans = KMeans(k=k, seed=42, featuresCol="features", predictionCol="AnomalyCluster")
    model = kmeans.fit(assembled)
    clustered = model.transform(assembled)

    # Mark the smallest cluster(s) as the "anomaly cluster"
    sizes = (clustered.groupBy("AnomalyCluster").count()
             .orderBy("count").limit(1).collect())
    anomaly_id = sizes[0]["AnomalyCluster"] if sizes else -1
    clustered = clustered.withColumn(
        "IsKMeansAnomaly",
        (F.col("AnomalyCluster") == F.lit(anomaly_id)).cast("int"),
    )
    return clustered.drop("features")


def train_isolation_forest(pdf: pd.DataFrame, contamination: float = 0.05) -> dict:
    pdf = pdf.dropna(subset=FEATURE_COLS).copy()
    X = pdf[FEATURE_COLS].to_numpy(dtype=np.float32)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)

    iso = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    ).fit(Xs)
    pred = (iso.predict(Xs) == -1).astype(int)  # 1 = anomaly

    y_true = _weak_label(pdf)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, pred, average="binary", zero_division=0
    )
    metrics = {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "n_anomalies_predicted": int(pred.sum()),
        "n_anomalies_weak_true": int(y_true.sum()),
        "contamination": contamination,
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(iso, ISO_MODEL)
    joblib.dump(scaler, ISO_SCALER)
    log_run(
        model_name="isolation_forest",
        params={"contamination": contamination, "features": FEATURE_COLS, "n_estimators": 200},
        metrics=metrics,
        stage="production",
    )
    return metrics


def score_isolation_forest(pdf: pd.DataFrame) -> np.ndarray:
    if not ISO_MODEL.exists():
        return np.zeros(len(pdf), dtype=int)
    iso: IsolationForest = joblib.load(ISO_MODEL)
    scaler: StandardScaler = joblib.load(ISO_SCALER)
    X = scaler.transform(pdf[FEATURE_COLS].fillna(0).to_numpy(dtype=np.float32))
    return (iso.predict(X) == -1).astype(int)
