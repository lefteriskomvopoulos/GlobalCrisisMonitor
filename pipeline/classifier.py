"""Spark MLlib classifiers for the QuadClass event-type label.

Trains and compares Random Forest, Logistic Regression, Decision Tree, and
Linear SVC (One-vs-Rest) on the GDELT feature set. The winning model
(highest weighted F1) is saved to disk and used to score the full table.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.classification import (
    DecisionTreeClassifier,
    LinearSVC,
    LogisticRegression,
    OneVsRest,
    RandomForestClassifier,
)
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import StringIndexer, VectorAssembler
from pyspark.sql import DataFrame

from config import FEATURE_COLS, MODELS_DIR
from pipeline.mlops import log_run

MODEL_DIR = MODELS_DIR / "spark_classifier"


def _model_for(name: str):
    if name == "logistic_regression":
        return LogisticRegression(labelCol="label", featuresCol="features", maxIter=20)
    if name == "decision_tree":
        return DecisionTreeClassifier(labelCol="label", featuresCol="features", maxDepth=8)
    if name == "linear_svc":
        return OneVsRest(
            classifier=LinearSVC(maxIter=20),
            labelCol="label",
            featuresCol="features",
        )
    return RandomForestClassifier(
        labelCol="label", featuresCol="features", numTrees=40, maxDepth=8, seed=42
    )


def _build_pipeline(model_name: str) -> Pipeline:
    indexer = StringIndexer(inputCol="QuadClass", outputCol="label", handleInvalid="skip")
    assembler = VectorAssembler(
        inputCols=FEATURE_COLS, outputCol="features", handleInvalid="skip"
    )
    return Pipeline(stages=[indexer, assembler, _model_for(model_name)])


def _evaluate(predictions: DataFrame) -> dict:
    metrics = {}
    for metric in ("accuracy", "weightedPrecision", "weightedRecall", "f1"):
        metrics[metric] = MulticlassClassificationEvaluator(
            labelCol="label", predictionCol="prediction", metricName=metric
        ).evaluate(predictions)
    return metrics


def train_all(df: DataFrame, candidates: list[str] | None = None) -> dict:
    candidates = candidates or [
        "random_forest",
        "logistic_regression",
        "decision_tree",
        "linear_svc",
    ]
    train, test = df.randomSplit([0.8, 0.2], seed=42)
    train.cache()
    test.cache()

    leaderboard: list[dict] = []
    best = None
    for name in candidates:
        print(f"[classifier] training {name}...")
        pipe = _build_pipeline(name)
        model = pipe.fit(train)
        preds = model.transform(test)
        metrics = _evaluate(preds)
        log_run(
            model_name=f"spark_{name}",
            params={"features": FEATURE_COLS, "split": "0.8/0.2"},
            metrics=metrics,
            stage="staging",
        )
        leaderboard.append({"model": name, "metrics": metrics})
        if best is None or metrics["f1"] > best["metrics"]["f1"]:
            best = {"name": name, "model": model, "metrics": metrics}

    # Persist winning model + promote to production
    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)
    best["model"].write().overwrite().save(str(MODEL_DIR))
    log_run(
        model_name=f"spark_{best['name']}",
        params={"features": FEATURE_COLS, "promoted": True},
        metrics=best["metrics"],
        stage="production",
    )
    train.unpersist()
    test.unpersist()
    return {"leaderboard": leaderboard, "best": {"name": best["name"], "metrics": best["metrics"]}}


def load() -> PipelineModel:
    return PipelineModel.load(str(MODEL_DIR))


def score(df: DataFrame) -> DataFrame:
    return load().transform(df)
