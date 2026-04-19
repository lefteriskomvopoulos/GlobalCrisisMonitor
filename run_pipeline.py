#!/usr/bin/env python3
"""End-to-end GDELT Crisis Monitor pipeline runner.

Stages (all idempotent, selectable via flags):

    1. ingest      — download & unzip GDELT 15-min exports
    2. etl         — Spark clean + partitioned warehouse
    3. classify    — Spark MLlib QuadClass classifiers (compare + promote)
    4. severity    — PyTorch regressor for severity score (MAE/RMSE)
    5. anomaly     — KMeans + IsolationForest anomaly detection (P/R)
    6. forecast    — Gradient Boosted tone forecaster (MAE/RMSE)
    7. export      — write dashboard parquet with all derived columns
    8. reports     — matplotlib/seaborn static PNG reports

Usage:
    python run_pipeline.py                        # full pipeline
    python run_pipeline.py --skip ingest          # reuse existing downloads
    python run_pipeline.py --only etl export      # re-run specific stages
    python run_pipeline.py --days-back 7 --max-files 192
    python run_pipeline.py --loop 30              # rerun every 30 min
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from datetime import datetime
from pathlib import Path

from pyspark.sql import functions as F

from config import DASHBOARD_DB, WAREHOUSE_DIR, METRICS_DIR
from pipeline import anomaly as anomaly_mod
from pipeline import analysis
from pipeline import classifier
from pipeline import deep_severity
from pipeline import forecast
from pipeline import ingest
from pipeline import preprocess
from pipeline.spark_session import get_spark

STAGES = ["ingest", "etl", "classify", "severity", "anomaly", "forecast",
          "export", "reports"]


def _should_run(stage: str, args: argparse.Namespace) -> bool:
    if args.only:
        return stage in args.only
    if args.skip:
        return stage not in args.skip
    return True


def _fmt_duration(sec: float) -> str:
    return f"{sec:.1f}s" if sec < 60 else f"{sec/60:.1f}m"


def run_once(args: argparse.Namespace) -> None:
    overall_start = time.time()
    timings: dict[str, float] = {}
    print(f"\n{'=' * 60}")
    print(f"Crisis Monitor pipeline — {datetime.now().isoformat(timespec='seconds')}")
    print(f"{'=' * 60}")

    # -------- Stage 1: ingest --------
    if _should_run("ingest", args):
        t = time.time()
        try:
            ingest.download_gdelt(
                days_back=args.days_back,
                max_files=args.max_files,
                workers=args.workers,
            )
        except Exception as e:
            print(f"[ingest] WARNING: {e}")
        timings["ingest"] = time.time() - t

    # -------- Stage 2: ETL --------
    if _should_run("etl", args):
        t = time.time()
        preprocess.run()
        timings["etl"] = time.time() - t

    spark = get_spark("CrisisMonitor-Run")
    events = spark.read.parquet(str(WAREHOUSE_DIR))
    row_count = events.count()
    print(f"[pipeline] warehouse rows loaded: {row_count:,}")

    # -------- Stage 3: classifier --------
    if _should_run("classify", args):
        t = time.time()
        classifier.train_all(events)
        timings["classify"] = time.time() - t

    # Read the warehouse directly with pandas for the sklearn/torch stages.
    # Avoids serializing a large Spark DataFrame back to the driver via py4j.
    pdf_cols = [
        "GlobalEventID", "QuadClass", "AvgTone", "GoldsteinScale",
        "NumSources", "NumArticles", "NumMentions",
        "CountryName", "ActionGeo_CountryCode",
        "ActionGeo_Lat", "ActionGeo_Long", "DateFormatted", "SOURCEURL",
    ]
    import pandas as pd
    pdf = pd.read_parquet(WAREHOUSE_DIR, columns=pdf_cols)
    pdf["DateFormatted"] = pd.to_datetime(pdf["DateFormatted"])

    # -------- Stage 4: severity (PyTorch) --------
    if _should_run("severity", args) and not pdf.empty:
        t = time.time()
        deep_severity.train(pdf, epochs=args.epochs)
        timings["severity"] = time.time() - t

    # -------- Stage 5: anomaly detection --------
    anomaly_metrics = None
    if _should_run("anomaly", args) and not pdf.empty:
        t = time.time()
        anomaly_metrics = anomaly_mod.train_isolation_forest(
            pdf, contamination=args.contamination
        )
        timings["anomaly"] = time.time() - t

    # -------- Stage 6: forecast --------
    forecast_metrics = None
    if _should_run("forecast", args) and not pdf.empty:
        t = time.time()
        forecast_metrics = forecast.train(pdf)
        timings["forecast"] = time.time() - t

    # -------- Stage 7: export dashboard parquet --------
    if _should_run("export", args) and not pdf.empty:
        t = time.time()
        tmp_root = Path(DASHBOARD_DB).parent / "_tmp_export"
        tmp_root.mkdir(parents=True, exist_ok=True)

        # 1) Deep-learning severity (primary score) + fallback rule-based
        try:
            pdf["SeverityPct"] = deep_severity.predict(pdf).round(2)
        except Exception as e:
            print(f"[export] falling back to rule-based severity ({e})")
            pdf["SeverityPct"] = deep_severity.compute_severity(pdf)
        pdf["SeverityPct"] = pdf["SeverityPct"].clip(0, 100)

        # 2) Anomaly flag (IsolationForest, pure pandas)
        pdf["IsAnomaly"] = anomaly_mod.score_isolation_forest(pdf)

        # 3) KMeans clustering via Spark — persist to parquet then merge in pandas
        km_path = tmp_root / "kmeans"
        if km_path.exists():
            import shutil as _sh
            _sh.rmtree(km_path)
        clustered = anomaly_mod.kmeans_cluster(events, k=5)
        (clustered.select("GlobalEventID", "AnomalyCluster", "IsKMeansAnomaly")
                  .write.mode("overwrite").parquet(str(km_path)))
        km = pd.read_parquet(km_path)
        pdf = pdf.merge(km, on="GlobalEventID", how="left")
        pdf["AnomalyCluster"] = pdf["AnomalyCluster"].fillna(-1).astype(int)
        pdf["IsKMeansAnomaly"] = pdf["IsKMeansAnomaly"].fillna(0).astype(int)

        # 4) Classifier prediction — same pattern (parquet handoff)
        try:
            cls_path = tmp_root / "classifier"
            if cls_path.exists():
                import shutil as _sh
                _sh.rmtree(cls_path)
            (classifier.score(events).select("GlobalEventID", "prediction")
                       .write.mode("overwrite").parquet(str(cls_path)))
            preds = (pd.read_parquet(cls_path)
                       .rename(columns={"prediction": "PredictedLabel"}))
            pdf = pdf.merge(preds, on="GlobalEventID", how="left")
            pdf["PredictedLabel"] = pdf["PredictedLabel"].fillna(-1).astype(int)
        except Exception as e:
            print(f"[export] classifier prediction skipped: {e}")
            pdf["PredictedLabel"] = -1

        # 5) Write dashboard parquet, partitioned by date (pure pandas/pyarrow)
        import pyarrow as pa
        import pyarrow.parquet as pq
        import shutil as _sh
        pdf["PartitionDate"] = pdf["DateFormatted"].dt.date.astype(str)
        if Path(DASHBOARD_DB).exists():
            _sh.rmtree(DASHBOARD_DB)
        Path(DASHBOARD_DB).mkdir(parents=True, exist_ok=True)
        pq.write_to_dataset(
            pa.Table.from_pandas(pdf, preserve_index=False),
            root_path=str(DASHBOARD_DB),
            partition_cols=["PartitionDate"],
        )

        # Clean up temp staging
        _sh.rmtree(tmp_root, ignore_errors=True)

        print(f"[export] dashboard_db rows: {len(pdf):,} "
              f"| dates: {pdf['PartitionDate'].nunique()}")
        timings["export"] = time.time() - t

    # -------- Stage 8: matplotlib/seaborn reports --------
    if _should_run("reports", args) and not pdf.empty:
        t = time.time()
        try:
            analysis.generate_all(pdf)
        except Exception as e:
            traceback.print_exc()
            print(f"[reports] WARNING: {e}")
        timings["reports"] = time.time() - t

    # -------- Done --------
    total = time.time() - overall_start
    timings["__total__"] = total
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    (METRICS_DIR / "pipeline_run.json").write_text(json.dumps(
        {"timings": timings, "row_count": row_count,
         "timestamp": datetime.utcnow().isoformat() + "Z",
         "anomaly": anomaly_metrics, "forecast": forecast_metrics},
        indent=2,
    ))

    print(f"\n{'=' * 60}")
    print("Stage timings:")
    for k, v in timings.items():
        if k != "__total__":
            print(f"  {k:<10} {_fmt_duration(v)}")
    print(f"  TOTAL     {_fmt_duration(total)}")
    print(f"{'=' * 60}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days-back", type=int, default=5,
                    help="download GDELT files from last N days (default 5)")
    ap.add_argument("--max-files", type=int, default=96,
                    help="cap number of 15-min export files (default 96 = ~1 day)")
    ap.add_argument("--workers", type=int, default=8,
                    help="parallel download workers")
    ap.add_argument("--epochs", type=int, default=40,
                    help="PyTorch training epochs for the severity net")
    ap.add_argument("--contamination", type=float, default=0.05,
                    help="IsolationForest contamination (expected anomaly fraction)")
    ap.add_argument("--skip", nargs="*", choices=STAGES, default=[],
                    help="stages to skip")
    ap.add_argument("--only", nargs="*", choices=STAGES, default=[],
                    help="run ONLY these stages")
    ap.add_argument("--loop", type=int, default=0,
                    help="if >0, re-run the pipeline every N minutes")
    args = ap.parse_args()

    while True:
        run_once(args)
        if args.loop <= 0:
            break
        print(f"[pipeline] sleeping {args.loop} min until next run...")
        time.sleep(args.loop * 60)


if __name__ == "__main__":
    main()
