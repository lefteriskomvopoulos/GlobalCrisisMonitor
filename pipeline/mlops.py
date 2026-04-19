"""Tiny MLOps tracker — appends each training run to a JSONL log.

Mirrors the spirit of an MLflow run table without the dependency: each
record carries a model name, parameters, timestamp, and metrics, so the
dashboard can plot a metric history across runs.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

from config import METRICS_DIR

RUNS_FILE = METRICS_DIR / "runs.jsonl"
LATEST_FILE = METRICS_DIR / "latest.json"


def log_run(model_name: str, params: dict, metrics: dict,
            stage: str = "production") -> dict:
    record = {
        "run_id": uuid.uuid4().hex[:12],
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "model": model_name,
        "stage": stage,
        "params": params,
        "metrics": metrics,
    }
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with RUNS_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")
    LATEST_FILE.write_text(json.dumps(record, indent=2))
    print(f"[mlops] logged run {record['run_id']} ({model_name}) -> {metrics}")
    return record


def load_history() -> list[dict]:
    if not RUNS_FILE.exists():
        return []
    with RUNS_FILE.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def latest() -> dict | None:
    if not LATEST_FILE.exists():
        return None
    return json.loads(LATEST_FILE.read_text())
