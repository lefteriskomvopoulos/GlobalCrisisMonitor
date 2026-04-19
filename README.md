# Global Event Sentiment & Spatial Analysis Pipeline

A distributed big-data pipeline that ingests the **GDELT 2.0 Event
Database**, runs Spark ETL into a Hive-style partitioned warehouse,
trains four classical ML classifiers + a PyTorch deep severity model +
sklearn anomaly / forecasting models, logs every run to a tiny MLOps
tracker, and renders the result through a five-tab Plotly Dash
dashboard.

> Spring 2026 CSGY-6513-C, Big Data — Rohit Shidid (rrs6770),
> Lefteris Komvopoulos (ek4538), Ron Zacharia (rrx2014)

---

## 1. What it does

| Stage | What happens | Key output |
|-------|-------------|------------|
| `ingest` | Downloads GDELT v2 15-min export ZIPs in parallel and unzips them. | `gdelt_data/`, `gdelt_data_unzipped/` |
| `etl`     | Spark reads every TSV, projects/casts to the analytics schema, drops bad rows, writes a Parquet warehouse partitioned by `PartitionDate / PartitionCountry`. | `warehouse/` + Spark SQL view `gdelt_events` |
| `classify` | Trains **Random Forest, Logistic Regression, Decision Tree, Linear SVC (OvR)** on the QuadClass label. Compares accuracy / weighted-precision / weighted-recall / F1 and promotes the winner to `models/spark_classifier`. | Spark MLlib model on disk |
| `severity` | A **PyTorch** feed-forward regressor learns a 0-100 severity score from `(AvgTone, GoldsteinScale, NumSources, NumArticles, NumMentions)`. MAE / RMSE on a held-out test split. | `models/severity_net.pt`, `severity_scaler.pkl` |
| `anomaly` | **KMeans** (Spark MLlib, k=5) flags the smallest cluster, plus **IsolationForest** (sklearn) reports precision / recall / F1 against a weak label drawn from statistical tails of tone & Goldstein. | `models/isoforest.pkl` |
| `forecast` | A **GradientBoostingRegressor** with lag-features predicts next-hour `AvgTone` per country on a temporal split. MAE / RMSE. | `models/tone_forecaster.pkl` |
| `export` | Joins severity, anomaly flags, KMeans cluster ids and classifier predictions into `dashboard_db/`, partitioned by date for fast dashboard reads. | `dashboard_db/PartitionDate=…/*.parquet` |
| `reports` | Static **matplotlib / seaborn** PNGs: top-N countries, tone-by-QuadClass violins, volume vs. severity time-series, feature correlation heatmap, anomaly breakdown. | `reports/*.png` |

Each training step is recorded to `metrics/runs.jsonl` (one JSON record
per run, with timestamp, model, params, stage, and metrics) so the
**Models** dashboard tab can plot a metric history.

---

## 2. Architecture

```
GDELT v2 master list ──▶  pipeline.ingest      (HTTP + zipfile, threaded)
                              │
                              ▼
                          gdelt_data_unzipped/*.CSV
                              │
                              ▼
                       pipeline.preprocess     (Spark ETL)
                              │
                              ▼
                          warehouse/         ←─ Hive-style partitioned Parquet
                          (PartitionDate=…/PartitionCountry=…)
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  pipeline.classifier  pipeline.deep_severity   pipeline.forecast
   (Spark MLlib RF /     (PyTorch FFN —          (sklearn GBR with
    LR / DT / OvR-SVC)    MAE/RMSE)               lag features)
        │                     │                     │
        └────────┬────────────┴────────┬────────────┘
                 ▼                     ▼
          pipeline.anomaly        pipeline.mlops
       (KMeans + IsoForest)      (runs.jsonl tracker)
                 │                     │
                 ▼                     ▼
            dashboard_db/         metrics/runs.jsonl
            (joined parquet)
                 │
                 ▼
              dashboard.py (Dash + Plotly)
        Map  •  Heatmap  •  Rankings  •  Anomalies  •  Models
```

---

## 3. Tech stack (all required by the proposal)

| Layer | What we use |
|-------|--------------|
| Programming | Python 3.9 |
| Distributed | PySpark 4.0 (local mode), Spark MLlib, Spark SQL warehouse |
| Storage | Parquet partitioned by `PartitionDate, PartitionCountry` (Hive-equivalent) |
| Deep learning | PyTorch 2.x (CPU / MPS) |
| Classical ML | Spark MLlib (RF, LR, DT, OvR-LinearSVC), KMeans; scikit-learn (IsolationForest, GradientBoostingRegressor, StandardScaler, train_test_split) |
| Visualisation | Plotly + Dash (interactive), matplotlib + seaborn (static reports) |
| Other | requests, pandas, numpy, joblib, pyarrow |

> Hive integration: the ETL writes to `spark_warehouse/` (configured as
> `spark.sql.warehouse.dir` with `enableHiveSupport()`) and registers a
> `gdelt_events` temp view backed by the partitioned Parquet path, so
> SQL queries push partition pruning the same way Hive does. No external
> metastore is required for the demo.

---

## 4. How to run

### One-time setup

```bash
cd "NYU Big data project"
python3.9 -m venv .venv          # if not already created
source .venv/bin/activate
pip install -r requirements.txt
```

You also need a JDK on `JAVA_HOME` for Spark. On macOS the pipeline
auto-discovers it via `/usr/libexec/java_home`; on Linux/Windows export
`JAVA_HOME` yourself.

### Run the full pipeline

```bash
python run_pipeline.py
```

Default flags pull the last **5 days × 96 files = ~1 day of global
events (~250–300k rows)** and run every stage. Total wall-clock on a
laptop: ~2.5 minutes.

### Useful flags

```bash
python run_pipeline.py --skip ingest                       # reuse cached CSVs
python run_pipeline.py --only etl export                   # rerun only those stages
python run_pipeline.py --days-back 7 --max-files 192       # bigger batch
python run_pipeline.py --epochs 80                         # train PyTorch longer
python run_pipeline.py --contamination 0.03                # tighter anomaly cutoff
python run_pipeline.py --loop 30                           # rerun every 30 min
```

Stages: `ingest`, `etl`, `classify`, `severity`, `anomaly`, `forecast`, `export`, `reports`.

### Launch the dashboard

```bash
python dashboard.py
# → http://127.0.0.1:8050
```

The dashboard auto-refreshes every 60 seconds, picks up new parquet
files written by `run_pipeline.py`, and toggles between dark / light
themes.

---

## 5. Dashboard tour

| Tab | Shows |
|-----|-------|
| **Map** | Global scatter map of events. Color + size = severity. Click any marker to open the source URL. (Down-sampled to the top-10k highest-severity events for performance.) |
| **Heatmap** | Country × hour severity heatmap (top 30 countries) plus a global volume vs. severity time-series. |
| **Rankings** | Top-25 countries by mean severity (bar) + CAMEO QuadClass distribution (pie). |
| **Anomalies** | Map of IsolationForest-flagged events, top-15 anomaly countries, and a sortable table of the highest-severity anomalies with clickable source links. |
| **Models** | Live MLOps view — F1 over time per Spark classifier, MAE/RMSE per regressor, IsolationForest precision / recall / F1, and a table of the most recent runs across every model. |

---

## 6. Project layout

```
NYU Big data project/
├── README.md                   ← this file
├── requirements.txt
├── config.py                   ← shared paths + GDELT schema
├── run_pipeline.py             ← CLI orchestrator (replaces old main.py)
├── dashboard.py                ← multi-tab Dash app
├── pipeline/
│   ├── spark_session.py        ← singleton Spark builder (Hive-enabled)
│   ├── ingest.py               ← parallel GDELT download + unzip
│   ├── preprocess.py           ← Spark ETL → partitioned Parquet warehouse
│   ├── classifier.py           ← Spark MLlib RF/LR/DT/SVC + leaderboard
│   ├── deep_severity.py        ← PyTorch FFN + StandardScaler
│   ├── anomaly.py              ← KMeans (Spark) + IsolationForest (sklearn)
│   ├── forecast.py             ← Gradient-boosted hourly tone forecaster
│   ├── analysis.py             ← matplotlib/seaborn static reports
│   └── mlops.py                ← runs.jsonl tracker + run promotion
├── gdelt_data/                 ← downloaded 15-min export ZIPs
├── gdelt_data_unzipped/        ← extracted TSVs
├── warehouse/                  ← Hive-style partitioned Parquet (analytics)
├── dashboard_db/               ← scored events ready for Dash
├── models/                     ← saved Spark / PyTorch / sklearn artifacts
├── metrics/                    ← runs.jsonl, latest.json, pipeline_run.json
├── reports/                    ← matplotlib/seaborn PNGs
└── spark_warehouse/            ← Hive-style metastore root for Spark SQL
```

---

## 7. Evaluation metrics (latest run)

The pipeline records all of the metrics called out in §7 of the
proposal. A representative run on ~267k events spanning five days:

| Model | Metric | Value |
|-------|--------|-------|
| Spark Random Forest        | accuracy / F1     | 0.919 / 0.917 |
| Spark Decision Tree        | accuracy / F1     | 0.920 / 0.916 |
| Spark Logistic Regression  | accuracy / F1     | 0.858 / 0.840 |
| Spark Linear SVC (OvR)     | accuracy / F1     | 0.752 / 0.650 |
| PyTorch SeverityNet        | MAE / RMSE        | 0.73 / 1.02 |
| GradientBoosted Forecaster | MAE / RMSE        | 2.67 / 3.50 |
| IsolationForest            | precision / recall / F1 | 0.40 / 0.16 / 0.22 |

> Numbers will vary across runs — every run is appended to
> `metrics/runs.jsonl` and visualised under the **Models** tab.

---

## 8. Troubleshooting

* **PySpark says `PYTHON_VERSION_MISMATCH`** — `pipeline/spark_session.py`
  pins `PYSPARK_PYTHON` / `PYSPARK_DRIVER_PYTHON` to `sys.executable`.
  If you launch the pipeline from a different interpreter, set those
  env vars manually.
* **`TaskResultLost (block manager)`** — driver memory is bumped to 4 GB
  with `spark.driver.maxResultSize=2g`. If you process even larger
  batches, raise both in `pipeline/spark_session.py`.
* **`JAVA_HOME` not set** — install a JDK and export `JAVA_HOME`. macOS
  is auto-detected via `/usr/libexec/java_home`.
* **Map tab is slow** — only the top-10k events are sent to Plotly. Edit
  `MAP_MAX_POINTS` in `dashboard.py` to change the cap.

---

## 9. Future work

The proposal's §9 extensions map cleanly onto the codebase:

* **Real-time streaming** — swap `pipeline.ingest` for a Spark Streaming
  / Kafka source pointing at the live GDELT 15-min feed.
* **Enhanced NLP** — fetch each event's `SOURCEURL`, run a transformer
  to compute embeddings / per-article tone, and feed the result into
  `pipeline.deep_severity`.
* **Alerts + auth** — wrap `dashboard.py` in Flask-Login and add a
  background task that posts to Slack when severity for a watched
  country crosses a configurable threshold.
