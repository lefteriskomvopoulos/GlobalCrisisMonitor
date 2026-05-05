// Build CS-GY 6513 final project report (DOCX).
// Run with: NODE_PATH=/opt/homebrew/lib/node_modules node build_report.js
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  ExternalHyperlink, TabStopType, TabStopPosition,
  PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo,
  PositionalTabLeader, TableOfContents, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak,
} = require('docx');

const ASSETS = path.join(__dirname, 'report_assets');

// ---------- helpers ----------
const P = (text, opts = {}) => new Paragraph({
  spacing: { after: 120 },
  ...opts,
  children: opts.children || [new TextRun({ text, ...opts.run })],
});

const H1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  pageBreakBefore: true,
  spacing: { before: 240, after: 240 },
  children: [new TextRun({ text })],
});

const H2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 240, after: 120 },
  children: [new TextRun({ text })],
});

const H3 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_3,
  spacing: { before: 200, after: 100 },
  children: [new TextRun({ text })],
});

const PARA = (text) => new Paragraph({
  spacing: { after: 140, line: 300 },
  alignment: AlignmentType.JUSTIFIED,
  children: [new TextRun({ text })],
});

const BULLET = (text) => new Paragraph({
  numbering: { reference: 'bullets', level: 0 },
  spacing: { after: 80, line: 280 },
  children: [new TextRun({ text })],
});

const NUM = (text) => new Paragraph({
  numbering: { reference: 'numbers', level: 0 },
  spacing: { after: 80, line: 280 },
  children: [new TextRun({ text })],
});

// monospace block paragraph with light-gray shading (manual padding via paragraph)
const CODE_LINE = (line) => new Paragraph({
  spacing: { after: 0, line: 240 },
  shading: { fill: 'F2F2F2', type: ShadingType.CLEAR },
  children: [new TextRun({ text: line || ' ', font: 'Consolas', size: 18 })],
});

// turn a multi-line code string into series of paragraphs
const CODE_BLOCK = (src) => {
  const lines = src.split('\n');
  return lines.map(CODE_LINE);
};

const CAPTION = (text) => new Paragraph({
  spacing: { before: 80, after: 200 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text, italics: true, size: 18, color: '555555' })],
});

const IMG = (filename, widthPx = 580, heightPx) => {
  const data = fs.readFileSync(path.join(ASSETS, filename));
  // auto height if not given (assume 16:10 landscape)
  const h = heightPx || Math.round(widthPx * 0.62);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 80 },
    children: [new ImageRun({
      type: filename.toLowerCase().endsWith('.png') ? 'png' : 'jpg',
      data,
      transformation: { width: widthPx, height: h },
      altText: { title: filename, description: filename, name: filename },
    })],
  });
};

const LINK = (label, url) => new Paragraph({
  spacing: { after: 100 },
  children: [new ExternalHyperlink({
    children: [new TextRun({ text: label, style: 'Hyperlink' })],
    link: url,
  })],
});

const SPACER = () => new Paragraph({ spacing: { after: 80 }, children: [new TextRun(' ')] });

// table cell helpers
const TD = (text, opts = {}) => new TableCell({
  width: { size: opts.width || 4680, type: WidthType.DXA },
  shading: opts.shade ? { fill: opts.shade, type: ShadingType.CLEAR } : undefined,
  margins: { top: 80, bottom: 80, left: 120, right: 120 },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: 'BBBBBB' },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: 'BBBBBB' },
    left: { style: BorderStyle.SINGLE, size: 4, color: 'BBBBBB' },
    right: { style: BorderStyle.SINGLE, size: 4, color: 'BBBBBB' },
  },
  children: [new Paragraph({
    spacing: { after: 0 },
    children: [new TextRun({ text, bold: !!opts.bold, size: opts.size || 20 })],
  })],
});

const TABLE = (rows, columnWidths) => new Table({
  width: { size: columnWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
  columnWidths,
  rows,
});

// ============================================================
// CONTENT
// ============================================================

// ---------- Title page ----------
const titlePage = [
  new Paragraph({ spacing: { after: 400 }, children: [new TextRun(' ')] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({
      text: 'CS-GY 6513: Big Data',
      bold: true, size: 36, color: '1F3864',
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 600 },
    children: [new TextRun({
      text: 'Spring 2026, Prof. Amit Patel',
      size: 24, color: '555555',
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
    children: [new TextRun({
      text: 'Final Project Report',
      bold: true, size: 28,
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 600 },
    children: [new TextRun({
      text: 'Global Event Sentiment & Spatial Analysis Pipeline',
      bold: true, size: 44, color: '111111',
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({
      text: '(GDELT Crisis Monitor)',
      italics: true, size: 24, color: '888888',
    })],
  }),
  new Paragraph({ spacing: { after: 600 }, children: [new TextRun(' ')] }),

  // Team table
  TABLE([
    new TableRow({ children: [
      TD('Name', { bold: true, shade: 'EEEEEE', width: 4680 }),
      TD('NetID', { bold: true, shade: 'EEEEEE', width: 4680 }),
    ]}),
    new TableRow({ children: [TD('Rohit Shidid', { width: 4680 }), TD('rrs6770', { width: 4680 })]}),
    new TableRow({ children: [TD('Lefteris Komvopoulos', { width: 4680 }), TD('ek4538', { width: 4680 })]}),
    new TableRow({ children: [TD('Ron Zacharia', { width: 4680 }), TD('rrx2014', { width: 4680 })]}),
  ], [4680, 4680]),

  new Paragraph({ spacing: { after: 400 }, children: [new TextRun(' ')] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({
      text: 'Semester: Spring 2026',
      size: 22, color: '555555',
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({
      text: 'Course: CS-GY 6513-C, Big Data',
      size: 22, color: '555555',
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({
      text: 'Submission date: May 2026',
      size: 22, color: '555555',
    })],
  }),
];

// ---------- Table of Contents ----------
const tocPage = [
  new Paragraph({ pageBreakBefore: true, heading: HeadingLevel.HEADING_1,
    children: [new TextRun('Table of Contents')] }),
  new TableOfContents('Table of Contents', { hyperlink: true, headingStyleRange: '1-3' }),
];

// ---------- 1. Executive Summary ----------
const executiveSummary = [
  H1('1. Executive Summary'),
  H2('1.1 Project name'),
  PARA('Global Event Sentiment & Spatial Analysis Pipeline. We refer to it internally as the GDELT Crisis Monitor, since that name fits the dashboard better than the formal one.'),
  H2('1.2 Brief summary'),
  PARA('GDELT publishes a fresh CSV of global news events every fifteen minutes. Each row is one event, with a country code, a latitude/longitude, a tone score, and a Goldstein conflict score, among about fifty other columns. We wrote a pipeline that downloads those CSVs, cleans them with PySpark, and writes them out to a Parquet warehouse partitioned by date and country. On top of that warehouse we train four Spark MLlib classifiers, a PyTorch regressor, an IsolationForest, and a gradient-boosted next-hour tone forecaster. The output of all of that feeds a five-tab Plotly Dash dashboard.'),
  PARA('On a 2024 MacBook Pro, the whole thing runs in about two and a half minutes for half a million events. The dashboard reads from disk on every callback and auto-refreshes once a minute, so as long as the pipeline keeps writing, the dashboard keeps updating without anyone restarting anything.'),
  H2('1.3 Objectives'),
  BULLET('Build a batch pipeline that downloads GDELT 15-minute exports and cleans them with PySpark.'),
  BULLET('Write the cleaned data to a partitioned Parquet warehouse so analytical queries can prune partitions instead of scanning the whole thing.'),
  BULLET('Pull tone, Goldstein, lat/long and country code from each event so we can cluster events both spatially and in feature space.'),
  BULLET('Train four Spark MLlib classifiers on the QuadClass label (Random Forest, Logistic Regression, Decision Tree, One-vs-Rest Linear SVC) plus a PyTorch regressor on a derived severity score. Log accuracy, weighted precision and recall, F1, MAE and RMSE for every run.'),
  BULLET('Add an anomaly layer (KMeans + IsolationForest) and a forecast layer (gradient-boosted next-hour tone). Report precision, recall and F1 for the anomaly layer against a weak label drawn from the tails of tone and Goldstein.'),
  BULLET('Put the whole thing behind a Dash app with a world map, country rankings, an anomaly worklist, and a Models tab that shows our training metrics over time.'),
  H2('1.4 Technologies used'),
  PARA('Everything is Python 3.9. We tested on macOS and Linux. Major picks:'),
  TABLE([
    new TableRow({ children: [TD('Layer', { bold: true, shade: 'EEEEEE' }), TD('Technology', { bold: true, shade: 'EEEEEE' })]}),
    new TableRow({ children: [TD('Distributed processing'), TD('Apache Spark 4.0 (PySpark, Spark MLlib, Spark SQL)')]}),
    new TableRow({ children: [TD('Storage / warehouse'), TD('Apache Parquet, Hive-style date+country partitioning')]}),
    new TableRow({ children: [TD('Schema & query catalog'), TD('Hive support enabled via spark.sql.warehouse.dir')]}),
    new TableRow({ children: [TD('Deep learning'), TD('PyTorch 2.x feed-forward regressor (CPU/MPS auto)')]}),
    new TableRow({ children: [TD('Classical ML'), TD('scikit-learn IsolationForest + GradientBoostingRegressor')]}),
    new TableRow({ children: [TD('Visualisation'), TD('Plotly + Dash, matplotlib + seaborn')]}),
    new TableRow({ children: [TD('Ingestion'), TD('Python requests + ThreadPoolExecutor (parallel HTTP)')]}),
    new TableRow({ children: [TD('Storage I/O'), TD('PyArrow + fastparquet for the pandas/Spark handoff')]}),
    new TableRow({ children: [TD('MLOps'), TD('JSONL run log, in-process tracker (mlflow-style schema)')]}),
  ], [4680, 4680]),
];

// ---------- 2. Code Execution Instructions ----------
const codeExecution = [
  H1('2. Code Execution Instructions'),
  PARA('Everything the pipeline writes lives inside the project folder. Raw TSVs, the warehouse, model files, the metrics log, the dashboard parquet and the matplotlib charts all sit next to each other under one tree. That means a fresh checkout plus a virtualenv is enough to reproduce the demo, with no external infrastructure to set up.'),
  H2('2.1 One-time environment setup'),
  PARA('We developed against Python 3.9 and a venv at the project root. PySpark needs a JDK on JAVA_HOME. On macOS, the SparkSession builder auto-discovers it via /usr/libexec/java_home. On Linux or Windows you have to export JAVA_HOME yourself before launching anything.'),
  ...CODE_BLOCK(`cd "NYU Big data project"
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt`),
  SPACER(),
  H2('2.2 Running the full pipeline'),
  PARA('With default flags the runner pulls the last five days of 15-minute exports (96 files, roughly 250 to 500 thousand rows depending on news volume) and runs every stage. Wall clock on a 2024 MacBook Pro is about two and a half minutes.'),
  ...CODE_BLOCK(`python run_pipeline.py`),
  SPACER(),
  PARA('Stages can be skipped or run in isolation via flags:'),
  ...CODE_BLOCK(`python run_pipeline.py --skip ingest                    # reuse cached CSVs
python run_pipeline.py --only etl export                # rerun only those stages
python run_pipeline.py --days-back 7 --max-files 192    # bigger batch
python run_pipeline.py --epochs 80                      # longer PyTorch training
python run_pipeline.py --contamination 0.03             # tighter anomaly cut-off
python run_pipeline.py --loop 30                        # rerun every 30 minutes`),
  SPACER(),
  PARA('There are eight pipeline stages: ingest, etl, classify, severity, anomaly, forecast, export, reports. Each one is idempotent. Re-running any stage overwrites cleanly, so if a run dies halfway through we just rerun the rest with --skip on the parts that finished.'),
  H2('2.3 Launching the dashboard'),
  ...CODE_BLOCK(`python dashboard.py
# → http://127.0.0.1:8050`),
  SPACER(),
  PARA('The Dash app re-reads dashboard_db/ on every callback. New parquet files written by run_pipeline.py are picked up automatically. There is a dark/light theme toggle in the top right, and a dcc.Interval triggers a refresh every sixty seconds.'),
  H2('2.4 README'),
  PARA('The README at the project root has the same setup instructions, an architecture diagram, the full directory tree, a troubleshooting section and the latest metrics:'),
  LINK('NYU Big data project/README.md', 'https://github.com/<your-handle>/NYU-Big-data-project/blob/main/README.md'),
  PARA('Swap <your-handle> for the GitHub user we push to before submission. The same file is included verbatim in the zip we hand in, at "NYU Big data project/README.md".'),
  H2('2.5 High-level code logic'),
  PARA('The codebase is laid out around four pieces: run_pipeline.py is the orchestrator, dashboard.py is the Dash app, config.py holds shared paths and the GDELT schema, and the pipeline/ package contains one module per pipeline stage. The orchestrator does almost nothing on its own. It parses arguments, calls into the pipeline modules in order, and writes per-stage timings to disk.'),
  ...CODE_BLOCK(`# run_pipeline.py — orchestrator skeleton
STAGES = ["ingest", "etl", "classify", "severity",
          "anomaly", "forecast", "export", "reports"]

def run_once(args):
    if _should_run("ingest", args):    ingest.download_gdelt(...)
    if _should_run("etl", args):       preprocess.run()
    spark  = get_spark("CrisisMonitor-Run")
    events = spark.read.parquet(str(WAREHOUSE_DIR))
    if _should_run("classify", args):  classifier.train_all(events)
    pdf = pd.read_parquet(WAREHOUSE_DIR, columns=pdf_cols)
    if _should_run("severity", args):  deep_severity.train(pdf)
    if _should_run("anomaly", args):   anomaly_mod.train_isolation_forest(pdf)
    if _should_run("forecast", args):  forecast.train(pdf)
    if _should_run("export", args):    _export(spark, events, pdf)
    if _should_run("reports", args):   analysis.generate_all(pdf)`),
  SPACER(),
  PARA('Every module in pipeline/ has a train() or run() entry point plus a load(), score() or predict() helper. We can retrain a model in one shell while another shell scores live data with the persisted version. That is the same training/inference split production systems use.'),
];

// ---------- 3. Architecture & data flow ----------
const architecture = [
  H1('3. Architecture & Data Flow'),
  PARA('We treat the pipeline as a chain of transformations where every stage writes its output to disk before the next one starts. The dashboard reads from the same files, so whatever the pipeline last wrote is what the UI shows.'),
  H2('3.1 End-to-end data flow'),
  ...CODE_BLOCK(`GDELT v2 master list (HTTP)
        │
        ▼
gdelt_data/*.zip          (parallel HTTP, 8 workers)
        │ unzip
        ▼
gdelt_data_unzipped/*.CSV (raw TSV, 61 cols)
        │ Spark read
        ▼
warehouse/                (Hive-style Parquet)
PartitionDate=…/PartitionCountry=…/part-*.parquet
        │
        ├── Spark MLlib classifier ─►   models/spark_classifier/
        ├── PyTorch SeverityNet     ─►  models/severity_net.pt
        ├── IsolationForest          ─► models/isoforest.pkl
        └── GradientBoosted forecast ─► models/tone_forecaster.pkl
        │
        ▼
KMeans (Spark) ─► temp Parquet ─► merge in pandas
        │
        ▼
dashboard_db/             (scored events, partitioned by date)
        │
        ▼
dashboard.py — Map / Heatmap / Rankings / Anomalies / Models`),
  SPACER(),
  PARA('Every box on that diagram is a directory on disk. Every arrow is one of the eight pipeline stages declared in run_pipeline.py. Two side outputs come out of every run: metrics/runs.jsonl (one JSON record per training, read by the Models tab) and metrics/pipeline_run.json (per-stage timings).'),
  H2('3.2 Stage-by-stage walkthrough'),
  H3('Stage 1: ingest (pipeline/ingest.py)'),
  PARA('We hit http://data.gdeltproject.org/gdeltv2/masterfilelist.txt, which lists every GDELT 15-minute export ever published. We filter by a days-back cutoff, take the top N URLs, and download them in parallel with a Python ThreadPoolExecutor. Each URL points to a ZIP that holds one tab-separated CSV. After the download loop finishes, we extract every ZIP into gdelt_data_unzipped/ and delete any ZIP that turned out to be corrupt, so a half-finished download cannot break the ETL stage that comes next.'),
  ...CODE_BLOCK(`# pipeline/ingest.py — parallel download
with ThreadPoolExecutor(max_workers=workers) as pool:
    futs = [pool.submit(_download_one, u, DOWNLOAD_DIR) for u in urls]
    for fut in as_completed(futs):
        res = fut.result()
        if res is not None:
            downloaded.append(res)`),
  SPACER(),
  H3('Stage 2: ETL (pipeline/preprocess.py)'),
  PARA('Spark reads every TSV with an explicit 61-column schema and the tab separator. Five to ten percent of rows have malformed numeric columns, so we use try_cast to turn bad strings into nulls instead of failing the whole job, then drop rows that are missing latitude, longitude, QuadClass, AvgTone or GoldsteinScale. We add two derived columns: PartitionDate (the calendar day) and PartitionCountry (the ActionGeo country code, defaulting to "UNK"), and write the result to warehouse/ as Parquet partitioned by both. The directory layout is the standard Hive form (PartitionDate=2026-04-19/PartitionCountry=US/part-*.parquet), so Spark can push partition filters down without any extra catalog setup.'),
  H3('Stage 3: classifier (pipeline/classifier.py)'),
  PARA('We train four Spark MLlib pipelines on the QuadClass label: Random Forest, Logistic Regression, Decision Tree, and One-vs-Rest LinearSVC. The feature vector is five columns: AvgTone, GoldsteinScale, NumSources, NumArticles, NumMentions. Each pipeline is just StringIndexer then VectorAssembler then the classifier. We split 80/20, score on accuracy, weighted precision and recall, and F1, and pick whichever model has the highest F1. The winner gets saved under models/spark_classifier/ and re-logged to the MLOps tracker with stage="production".'),
  H3('Stage 4: severity (pipeline/deep_severity.py)'),
  PARA('A PyTorch feed-forward regressor learns a 0 to 100 severity score we derived from tone magnitude, the inverted Goldstein scale (more negative meaning more conflict potential), and a log-scaled volume term. The network is small: 5 inputs to 64, then 32, then a single output, with ReLU activations and one Dropout layer. The training loop is plain PyTorch with Adam and MSE loss, 25 to 40 epochs depending on the flag. The device is picked automatically: CUDA if available, otherwise Apple MPS, otherwise CPU. We record MAE and RMSE on a held-out 20 percent test set.'),
  H3('Stage 5: anomaly detection (pipeline/anomaly.py)'),
  PARA('Two models do this together. KMeans (Spark MLlib, k=5) clusters events in feature space and we flag the smallest cluster as IsKMeansAnomaly = 1. IsolationForest (sklearn, 200 trees, contamination 0.05) gives every row an outlier score. Then we score against a weak label derived from the tails of tone and Goldstein (|z| > 2) so we have something to compute precision, recall, and F1 against. The Models tab plots how those numbers change across runs.'),
  H3('Stage 6: forecast (pipeline/forecast.py)'),
  PARA('A scikit-learn GradientBoostingRegressor predicts the next-hour AvgTone per country. The features are lags at 1, 2, 3, 6 and 12 hours, a 3-hour rolling mean, hour-of-day, day-of-week, and the event count for that country in that hour. We split temporally: the last 20 percent of hours go into the test set. That keeps future data out of training.'),
  H3('Stage 7: export (run_pipeline.py)'),
  PARA('The export stage joins everything into one wide Parquet table for the dashboard. PyTorch severity becomes a column, IsolationForest becomes a 0/1 flag, and the Spark KMeans cluster ID and Spark classifier prediction get merged in. Two of those joins start in Spark and the rest in pandas, so we use a Parquet hand-off: Spark writes the bits we need to a temp Parquet directory, pandas reads them back with PyArrow, does the merge in memory, and writes the final dashboard_db/ partitioned by date. We added this hand-off only after an earlier version blew up with a driver OOM trying to toPandas() the full 500k-row frame.'),
  ...CODE_BLOCK(`# run_pipeline.py — Parquet handoff to dodge driver-side OOM
clustered = anomaly_mod.kmeans_cluster(events, k=5)
(clustered.select("GlobalEventID", "AnomalyCluster", "IsKMeansAnomaly")
          .write.mode("overwrite").parquet(str(km_path)))
km  = pd.read_parquet(km_path)
pdf = pdf.merge(km, on="GlobalEventID", how="left")`),
  SPACER(),
  H3('Stage 8: reports (pipeline/analysis.py)'),
  PARA('Five static PNGs come out of matplotlib and seaborn and land in reports/. They are also reproduced in Appendix A so the report has a self-contained visual record of whatever the warehouse looked like at the time of the run.'),
];

// ---------- 4. Big Data Concepts ----------
const bigDataConcepts = [
  H1('4. Big Data Concepts in Use'),
  PARA('The demo runs on one laptop, but we built it around the same patterns a real cluster would use. The table below maps every big-data concept the project exercises to the file or function in the codebase where you can see it.'),
  TABLE([
    new TableRow({ children: [TD('Concept', { bold: true, shade: 'EEEEEE', width: 3000 }), TD('Where applied in the codebase', { bold: true, shade: 'EEEEEE', width: 6360 })]}),
    new TableRow({ children: [TD('Distributed compute', { width: 3000 }), TD('Spark local[*] master spawns one executor per CPU core; ETL, KMeans, classifier training all shuffle across them.', { width: 6360 })]}),
    new TableRow({ children: [TD('Columnar storage', { width: 3000 }), TD('Parquet (Snappy compressed) is used for both warehouse/ and dashboard_db/. Compresses ~110 MB TSV → ~65 MB Parquet, allows column projection at read time.', { width: 6360 })]}),
    new TableRow({ children: [TD('Hive-style partitioning', { width: 3000 }), TD('Two-level directory partitioning by PartitionDate and PartitionCountry; Spark prunes partitions on filter push-down without any extra config.', { width: 6360 })]}),
    new TableRow({ children: [TD('Hive metastore integration', { width: 3000 }), TD('SparkSession built with enableHiveSupport() and a configured spark.sql.warehouse.dir; the cleaned warehouse is registered as a temp view "gdelt_events" so the same SQL queries that work in beeline work here.', { width: 6360 })]}),
    new TableRow({ children: [TD('Schema-on-read', { width: 3000 }), TD('Raw GDELT TSVs have no embedded schema. A 61-column StructType is applied at read time and try_cast is used per field to keep bad rows alive.', { width: 6360 })]}),
    new TableRow({ children: [TD('ETL', { width: 3000 }), TD('Three classic phases: extract (HTTP), transform (Spark SQL try_cast / filter / project), load (partitioned Parquet).', { width: 6360 })]}),
    new TableRow({ children: [TD('Distributed ML', { width: 3000 }), TD('Spark MLlib Pipelines for the four classifiers and KMeans. No driver-side collect; everything stays as RDDs/DataFrames.', { width: 6360 })]}),
    new TableRow({ children: [TD('Lambda-style separation', { width: 3000 }), TD('Heavy distributed work in Spark, light per-row scoring in pandas / sklearn / PyTorch. Parquet is the lingua franca between the two.', { width: 6360 })]}),
    new TableRow({ children: [TD('Idempotent stages', { width: 3000 }), TD('Every stage overwrites cleanly. --skip / --only flags allow surgical reruns. Crash-safe: a half-finished pipeline can be resumed from any stage.', { width: 6360 })]}),
    new TableRow({ children: [TD('MLOps tracking', { width: 3000 }), TD('Append-only metrics/runs.jsonl records every training (RF, LR, DT, SVC, PyTorch, IsoForest, forecaster). Models are promoted from "staging" to "production" stages.', { width: 6360 })]}),
    new TableRow({ children: [TD('Parallel I/O', { width: 3000 }), TD('Eight-worker ThreadPoolExecutor for the GDELT download phase saturates network I/O without overwhelming the GDELT servers.', { width: 6360 })]}),
    new TableRow({ children: [TD('Throughput measurement', { width: 3000 }), TD('Per-stage timings recorded to metrics/pipeline_run.json so we can answer the proposal\'s evaluation question of how long it takes to process N rows.', { width: 6360 })]}),
    new TableRow({ children: [TD('Driver-memory escape hatch', { width: 3000 }), TD('Spark to pandas hand-off through temporary Parquet instead of toPandas(). Sidesteps TaskResultLost and Arrow overflow at scale.', { width: 6360 })]}),
  ], [3000, 6360]),
  PARA('Section 5 picks up several of these threads. The partitioning strategy and the Parquet hand-off in particular drove a lot of the final design.'),
];

// ---------- 5. Technological Challenges ----------
const challenges = [
  H1('5. Technological Challenges'),
  PARA('The project went through several rewrites during development. Each one came out of an actual failure mode we hit only after we scaled the dataset up. Each one taught us something specific about how PySpark behaves on a real machine versus how it looks in tutorials.'),
  H2('5.1 PySpark worker / driver Python version mismatch'),
  PARA('Symptom: training the Linear SVC classifier blew up with PYSPARK_RUNTIME_ERROR. The actual message read "Python in worker has different version: 3.13 than that in driver: 3.9, PySpark cannot run with different minor versions." The cause: PySpark spawns its Python workers using whatever python3 happens to be on PATH. On macOS that is usually the system Python, not the venv interpreter the driver is running.'),
  PARA('Fix: pipeline/spark_session.py pins PYSPARK_PYTHON and PYSPARK_DRIVER_PYTHON to sys.executable before the SparkSession is built. Workers now use the same interpreter as the driver. The whole fix is two lines, but the bug is invisible until something triggers a Python UDF, which is exactly the type of issue that does not show up in a unit test and only bites in real runs.'),
  ...CODE_BLOCK(`# pipeline/spark_session.py — pin worker interpreter
def _pin_pyspark_python() -> None:
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)`),
  SPACER(),
  H2('5.2 Driver TaskResultLost when materialising large DataFrames'),
  PARA('Symptom: once we scaled the dataset from one day to five days, the export stage crashed with TaskResultLost (block manager) or an Arrow IOException at toPandas(). The Spark driver could not hold a quarter-million-row Arrow batch in memory long enough to round-trip it through py4j.'),
  PARA('Fix: every Spark to pandas hand-off in the export stage now goes through a temporary Parquet directory. Spark writes the small projection it needs to share, and pandas reads that back with PyArrow. We left this pattern explicit in the code so anyone reading run_pipeline.py later sees that it is intentional, not laziness. The temp Parquet also doubles as a debugging hook because we can inspect it on disk between runs.'),
  H2('5.3 Hive-style partitions invisible to CREATE TABLE OPTIONS(path)'),
  PARA('Symptom: after the ETL wrote out PartitionDate=.../PartitionCountry=... directories, the query SELECT COUNT(DISTINCT PartitionDate) FROM gdelt_events returned zero rows. The reason: CREATE TABLE ... USING PARQUET OPTIONS(path ...) in Spark SQL does not auto-discover partitions. It treats the directory as a flat file.'),
  PARA('Fix: pipeline/preprocess.py registers the warehouse as a temp view via spark.read.parquet().createOrReplaceTempView("gdelt_events") instead. The Parquet reader auto-infers the partition columns and pushes filters down correctly.'),
  H2('5.4 Plotly browser chokes on half a million scatter points'),
  PARA('Symptom: our first end-to-end run produced a 73 MB JSON payload for the Map tab. Plotly was trying to render 250,000 SVG circles in the browser. Chrome was unhappy. Time to interactive crept past ten seconds, and the colour scale ramp rendered before the markers did.'),
  PARA('Fix: dashboard.py defines MAP_MAX_POINTS = 10000 and a tiny _downsample_for_map helper. It keeps the top-severity half of the events deterministically (the visual story is preserved) and randomly samples the rest. The same helper is used on the Anomalies tab with a smaller cap of 6000. The map response dropped from 73 MB to 2.7 MB. The tab now feels instant.'),
  ...CODE_BLOCK(`# dashboard.py — keep the top-N severity, sample the rest
def _downsample_for_map(df, cap=MAP_MAX_POINTS):
    if len(df) <= cap:  return df
    top  = df.nlargest(cap // 2, "SeverityPct")
    rest = df.drop(top.index).sample(n=cap - cap // 2, random_state=42)
    return pd.concat([top, rest], ignore_index=True)`),
  SPACER(),
  H2('5.5 Python 3.9 vs PEP 604 union types'),
  PARA('Symptom: a module-level annotation like _session: SparkSession | None = None raised TypeError: unsupported operand type(s) for |: \'type\' and \'NoneType\'. The pipe-union syntax is PEP 604, which only became valid at runtime in Python 3.10. We were on 3.9.'),
  PARA('Fix: every module in the pipeline package now starts with from __future__ import annotations. That defers annotation evaluation to string form, so PEP 604 syntax inside type hints is legal under 3.9. Module-level variable annotations (which the __future__ import does not defer) we rewrote to use Optional[SparkSession] instead.'),
  H2('5.6 Memory pressure during multi-classifier training'),
  PARA('Symptom: training all four classifiers back-to-back on a cached Spark DataFrame triggered repeated TaskResultLost errors. Each fit was producing intermediate predictions that did not get freed in time. Fix: pandas no longer reads from the cached events DataFrame at all. It reads the partitioned Parquet directly. That one change made the whole downstream PyTorch and sklearn chain stable at every dataset size we tested up to ~600k rows.'),
];

// ---------- 6. Changes in Technology ----------
const changes = [
  H1('6. Changes in Technology'),
  PARA('The proposal called for Hadoop 3.4.2 with HDFS, MapReduce, PySpark, and Hive as the big-data stack, plus PyTorch and scikit-learn for ML and matplotlib with seaborn (and maybe React) for visualisation. We followed most of that list. Five things ended up different. This section explains what we changed and why.'),
  H2('6.1 Hadoop / HDFS replaced by local Spark + Hive-style Parquet'),
  PARA('Proposed: raw data uploaded to HDFS, queries served through Hive. Built: data sits on the local filesystem in a Parquet warehouse partitioned by date and country. SparkSession is built with enableHiveSupport() and a real spark.sql.warehouse.dir on disk. Why: standing up an HDFS cluster locally would have meant booting NameNode/DataNode containers and keeping them alive across restarts, and the graders would have needed the same infrastructure to reproduce the demo. The Parquet warehouse gives us the same query semantics: partition pruning, column projection, predicate push-down. We describe the future work (single-node HDFS in docker-compose) in section 9.'),
  H2('6.2 MapReduce dropped in favour of Spark transformations'),
  PARA('Proposed: explicit MapReduce jobs. Built: every aggregation is a Spark DataFrame or SQL operation. Spark plans and executes those as MapReduce-style shuffles under the hood via Catalyst. We thought about writing one Hadoop-streaming job (an actor-name word count, say) just to be literal about the proposal, but the time was better spent on the PyTorch model and the dashboard.'),
  H2('6.3 Plotly Dash chosen over a separate React frontend'),
  PARA('Proposed: matplotlib, seaborn, possibly React. Built: a Plotly Dash dashboard with five tabs and a dark/light theme toggle, plus the static matplotlib charts in reports/. Why: Dash gave us interactive maps, click-to-open source URLs, an auto-refresh interval, and a native MLOps view in about 500 lines of Python. A React frontend with a separate REST API would have needed another two people on the team and would not have made the underlying analysis any better.'),
  H2('6.4 sklearn IsolationForest + GradientBoosted forecaster added'),
  PARA('Proposed: deep-learning models for both sentiment classification and anomaly detection. Built: the PyTorch network handles severity regression. Anomaly detection uses sklearn IsolationForest, and forecasting uses sklearn GradientBoostingRegressor. Why: IsolationForest is the right tool for unsupervised outlier detection on tabular features. It also trains in seconds where a Random Forest of comparable depth takes minutes. For the per-country forecaster we have less than 1000 rows of hourly history per country, which is too little for an LSTM to outperform a gradient-boosted baseline with lag features.'),
  H2('6.5 In-process JSONL MLOps tracker instead of MLflow'),
  PARA('Proposed: track every training run for reproducibility. Built: a 40-line MLOps module that appends a JSON record per training to metrics/runs.jsonl and republishes the most recent one to metrics/latest.json. Why: MLflow needs either a local UI server or an external tracking backend, both of which add deployment surface area. The JSONL tracker captures the same essentials (run_id, timestamp, model name, parameters, metrics, stage) and the Models tab of the dashboard plots them directly. We get the MLflow-style metric-over-time view without the extra service.'),
];

// ---------- 7. Uncovered aspects from presentation (with screenshots) ----------
const uncovered = [
  H1('7. Uncovered Aspects from the Presentation'),
  PARA('Fifteen minutes is enough to walk through the architecture diagram, run the pipeline once, and demo the Map tab. It is not enough to talk through every dashboard tab or every metric the pipeline produces. This section covers the screens and outputs we had to skip during the live demo.'),
  H2('7.1 The global map (Map tab, dark theme)'),
  IMG('01_map_dark.png', 580),
  CAPTION('Figure 7.1: Map tab. Each marker is one GDELT event. Colour and size encode severity. Down-sampled to 10,000 markers out of the full 518,234 so the browser stays responsive.'),
  PARA('Severity is the 0 to 100 score the PyTorch SeverityNet assigns to every event. The colour ramp runs from cream at low severity to deep red at the top. Even with only 10,000 markers visible, you can read the geography: heavy clusters on the US east coast and across Europe, secondary hotspots in South and East Asia, and a much sparser tail of coverage across Africa and South America.'),
  PARA('The KPI strip in the page header (visible across every screenshot in this section) tracks four counters: warehouse rows, dashboard rows, total anomalies plus average severity, and how many distinct countries are represented. These get recomputed on every callback, so they are always current.'),
  H2('7.2 Click-to-source URL on the Map'),
  IMG('02_map_zoom_nyc.png', 580),
  CAPTION('Figure 7.2: zoomed Map view over New York with the Plotly hover tooltip open. The tooltip shows location, severity, anomaly cluster ID, and timestamp. Clicking a marker opens the source URL.'),
  PARA('The Plotly toolbar across the top right gives you pan, zoom, lasso, and a one-click PNG export. Our custom click handler reads the marker\'s SOURCEURL attribute and renders it as an external link in the panel under the map. That single feature is what turns the dashboard from a chart into a triage tool. An analyst can go from the world map to the underlying news article in two clicks.'),
  H2('7.3 Heatmap tab: country by hour severity, plus global volume'),
  IMG('03_heatmap.png', 580),
  CAPTION('Figure 7.3: Heatmap tab. The top panel pivots the 30 highest-severity locations against the hourly time axis (red = high severity). The bottom panel overlays global event volume (blue, left axis) on top of mean severity (red, right axis).'),
  PARA('The pivot on top shows where, and when, the worst events clustered during the active window. We did not pick the two outlier rows (Cumberland County in Kentucky, and Tagab in Farah province in Afghanistan). The PyTorch model surfaced them on its own because they sustained a high severity score across many hours. The bottom panel is more of a sanity check: blue is raw volume per hour, red is mean severity. They usually track each other loosely. When the red line decouples upward (the spike in mid April), that means coverage skewed toward heavy events that hour, which is normally worth a closer look.'),
  H2('7.4 Rankings tab: top countries and CAMEO QuadClass distribution'),
  IMG('04_rankings_full.png', 580),
  CAPTION('Figure 7.4: Rankings tab, overview. The bar chart shows the top 25 countries by mean severity over the active window. The pie at the bottom breaks events down by CAMEO QuadClass (Verbal/Material x Cooperation/Conflict).'),
  PARA('Even on a heavy news week, most GDELT events fall into QuadClass 1 (Verbal Cooperation). The remaining three classes split the long tail. That is a useful base rate to know about. Any classifier that beats "always predict QuadClass 1" (about 62 percent accuracy) is doing real work, and our Random Forest at 91.9 percent accuracy clears that bar by a wide margin.'),
  IMG('05_rankings_zoom.png', 580),
  CAPTION('Figure 7.5: Rankings tab zoomed to the top 10. The Plotly hover tooltip exposes event count and mean tone for every bar. Mount Auburn, Ohio is the highest-severity location with 4 events and a mean tone of -22.32.'),
  PARA('A mean tone of -22 is about three standard deviations below the global mean. These are not "slightly negative" stories; they are the most dramatic events in the warehouse. Hovering over a country in the demo is the fastest way to take its temperature without leaving the dashboard.'),
  H2('7.5 Anomalies tab: flagged events, top countries, drill-down table'),
  IMG('06_anomalies.png', 580),
  CAPTION('Figure 7.6: Anomalies tab. Upper map shows every IsolationForest-flagged event (down-sampled to 6,000). Middle panel is the top-15 location bar. Bottom is a sortable table of the highest-severity anomalies with clickable source URLs.'),
  PARA('This is the third triage view. The upper map tells you at a glance where the outliers cluster (heavy in North America and South Asia in this run). The bar chart names the 15 most-affected locations. The bottom table is a literal worklist: sort by any column, click the URL, read the article.'),
  H2('7.6 Models tab: MLOps view across runs'),
  IMG('07_models.png', 580),
  CAPTION('Figure 7.7: Models tab. Trends in Spark classifier F1, regressor MAE and RMSE, and IsolationForest precision, recall and F1 across every training run, with a "Recent runs" table at the bottom.'),
  PARA('Every model the pipeline trains (any of the seven) appends a JSON record to metrics/runs.jsonl. The Models tab reads that file, melts it into long form, and renders three Plotly line charts plus the leaderboard table. It does the same job MLflow UI would, but it ships with the dashboard, needs no separate server, and stays in sync with whatever the rest of the pipeline last wrote.'),
  H2('7.7 Light theme'),
  IMG('08_map_light.png', 580),
  CAPTION('Figure 7.8: same Map tab after toggling the light theme. Plotly Carto Positron tiles replace Carto Darkmatter, the page chrome flips colour, and the marker colour scale is unchanged so the visual story stays the same.'),
  PARA('Dark is the default because demos usually run in a dim room. The toggle in the header flips the tile style, page background, foreground colour, and the Plotly template all together so the dashboard never ends up half dark and half light.'),
];

// ---------- 8. Lessons learned ----------
const lessons = [
  H1('8. Lessons Learned'),
  H2('8.1 Treat the Spark/pandas boundary as a design decision'),
  PARA('The biggest lesson from this project: toPandas() is a memory cliff at scale, and the answer is not "give the driver more RAM." The answer is to make the hand-off explicit by writing to Parquet and reading back. Once we made that change, everything downstream (the PyTorch model, IsolationForest, the forecaster, the dashboard parquet) just worked. Half a million rows is not big data by anyone\'s definition, but the same discipline that made our code stable at that scale is what would let it run on half a billion across a real cluster.'),
  H2('8.2 Idempotent stages saved us hours of iteration time'),
  PARA('Every stage in run_pipeline.py is idempotent and can be skipped or run alone via flags. We added that as a polish item early on, and it turned out to be the biggest productivity win of the project. During PyTorch tuning we re-ran only --only severity, dozens of times. During dashboard polish we re-ran only --only export. End-to-end takes about 2.5 minutes; the inner-loop runs take 5 to 25 seconds. That is the gap between iterating fluidly and waiting for a build.'),
  H2('8.3 Hive-style partitioning pays off even on a laptop'),
  PARA('We added PartitionDate by PartitionCountry partitioning because the proposal asked for partitioning by date and country. We expected the only payoff to be partition-pruned queries. In practice it also shrank the dashboard\'s Parquet reads (the dashboard only needs the most recent dates), made it trivial to drop a single bad ingestion day without touching the rest of the warehouse, and gave us a directory-level view of how data is distributed across countries for free.'),
  H2('8.4 Fail safely, log the blame loud'),
  PARA('When the PyTorch model file is missing, the export stage falls back to the rule-based severity score and prints why. When the Spark classifier prediction errors out, the export stage skips it and warns. That degrade-gracefully pattern is what saved us several times during late-night dashboard checks. A half-broken dashboard is much less embarrassing than a black screen during grading.'),
  H2('8.5 Pin every runtime decision to the venv'),
  PARA('PYSPARK_PYTHON, JAVA_HOME, the venv interpreter, the PyTorch device. Every single one of those is decided in one place: pipeline/spark_session.py at SparkSession creation. That single file made the project actually portable across the three laptops we developed on, instead of "works on my machine" three different times.'),
];

// ---------- 9. Future improvements ----------
const future = [
  H1('9. Future Improvements'),
  PARA('With more time, the next features we would build would push the project deeper into big-data engineering territory and give the analysis side richer inputs to learn from.'),
  H2('9.1 Real-time streaming via Kafka and Spark Structured Streaming'),
  PARA('The single biggest upgrade is moving the batch ingestion to a real-time stream. GDELT publishes a fresh export every 15 minutes. A Kafka topic in front of a Spark Structured Streaming reader would turn run_pipeline.py from a polled batch job into a continuously running pipeline whose warehouse updates live with the global news cycle. The dashboard would only need to point at the latest dashboard parquet partition for the update to flow through.'),
  H2('9.2 Medallion (Bronze / Silver / Gold) data-lake architecture'),
  PARA('Right now we have one warehouse/ directory. A medallion split (Bronze for raw schema-on-read, Silver for cleaned and partitioned which is what we have now, Gold for pre-aggregated country-by-hour summaries) would map onto the same storage with two extra Spark jobs. It would give every downstream consumer a stable contract and would let the dashboard skip the aggregation work it currently does at request time.'),
  H2('9.3 Delta Lake (or Apache Iceberg) on top of Parquet'),
  PARA('A small change. Install delta-spark, switch .format("parquet") to .format("delta") on the ETL writer. That would give us ACID transactions on the warehouse, schema evolution, and (most usefully) "VERSION AS OF" time-travel queries. We could add a "view warehouse as of yesterday\'s run" toggle to the dashboard. That is the kind of thing analysts ask for first.'),
  H2('9.4 Pseudo-distributed HDFS + real Hive metastore via docker-compose'),
  PARA('To honour the proposal literally, a docker-compose with one HDFS NameNode, two DataNodes, a Hive metastore and a Spark master plus workers would let the warehouse live on hdfs://... and be queryable through beeline. Same code, real infrastructure.'),
  H2('9.5 Enhanced NLP on the source URLs'),
  PARA('The dashboard already exposes the SOURCEURL of every event. The next step is to fetch each article, run a model like RoBERTa to produce a fresh tone score from the actual text, and back-populate the warehouse. The PyTorch severity head would then learn from a 768-dim embedding instead of five scalar features. We would expect MAE to drop substantially.'),
  H2('9.6 Alerting and authentication'),
  PARA('A small Flask layer in front of the Dash app for SSO and per-user alert thresholds would turn the tool into something a working analyst would log into every morning. A background task that emails or Slacks an alert when severity for a watched country crosses a threshold would close the loop from "interesting chart" to "ping me when this matters".'),
  H2('9.7 Model ensembling'),
  PARA('The Spark MLlib leaderboard already picks the highest-F1 model and promotes it. A simple stacking ensemble (a Logistic Regression second-stage that takes the four base-model probability vectors as input) would likely buy us another point of F1 with no new training data.'),
];

// ---------- 10. Data sources & results (charts) ----------
const dataResults = [
  H1('10. Data Sources & Results'),
  H2('10.1 Code repository'),
  PARA('The code we ship is the same project directory we use for the live demo. We will publish the repository to GitHub before submission; the URL will be:'),
  LINK('https://github.com/<your-handle>/NYU-Big-data-project', 'https://github.com/<your-handle>/NYU-Big-data-project'),
  H2('10.2 Data sources'),
  TABLE([
    new TableRow({ children: [TD('Resource', { bold: true, shade: 'EEEEEE', width: 3000 }), TD('URL / location', { bold: true, shade: 'EEEEEE', width: 6360 })]}),
    new TableRow({ children: [TD('GDELT v2 master file list', { width: 3000 }), TD('http://data.gdeltproject.org/gdeltv2/masterfilelist.txt', { width: 6360 })]}),
    new TableRow({ children: [TD('GDELT project home', { width: 3000 }), TD('https://www.gdeltproject.org/', { width: 6360 })]}),
    new TableRow({ children: [TD('CAMEO event codes', { width: 3000 }), TD('https://www.gdeltproject.org/data.html#documentation', { width: 6360 })]}),
    new TableRow({ children: [TD('Apache Spark docs', { width: 3000 }), TD('https://spark.apache.org/docs/latest/', { width: 6360 })]}),
    new TableRow({ children: [TD('Plotly Dash', { width: 3000 }), TD('https://dash.plotly.com/', { width: 6360 })]}),
  ], [3000, 6360]),
  H2('10.3 Latest evaluation metrics'),
  PARA('The pipeline records every metric the proposal asked for in section 7. A representative end-to-end run on 518,234 events spanning roughly five days of global news gave us the following:'),
  TABLE([
    new TableRow({ children: [TD('Model', { bold: true, shade: 'EEEEEE', width: 4000 }), TD('Metric', { bold: true, shade: 'EEEEEE', width: 2500 }), TD('Value', { bold: true, shade: 'EEEEEE', width: 2860 })]}),
    new TableRow({ children: [TD('Spark Random Forest', { width: 4000 }), TD('accuracy / F1', { width: 2500 }), TD('0.919 / 0.917', { width: 2860 })]}),
    new TableRow({ children: [TD('Spark Decision Tree', { width: 4000 }), TD('accuracy / F1', { width: 2500 }), TD('0.920 / 0.916', { width: 2860 })]}),
    new TableRow({ children: [TD('Spark Logistic Regression', { width: 4000 }), TD('accuracy / F1', { width: 2500 }), TD('0.858 / 0.840', { width: 2860 })]}),
    new TableRow({ children: [TD('Spark Linear SVC (One-vs-Rest)', { width: 4000 }), TD('accuracy / F1', { width: 2500 }), TD('0.752 / 0.650', { width: 2860 })]}),
    new TableRow({ children: [TD('PyTorch SeverityNet', { width: 4000 }), TD('MAE / RMSE', { width: 2500 }), TD('0.73 / 1.02', { width: 2860 })]}),
    new TableRow({ children: [TD('GradientBoosted tone forecaster', { width: 4000 }), TD('MAE / RMSE', { width: 2500 }), TD('2.67 / 3.50', { width: 2860 })]}),
    new TableRow({ children: [TD('IsolationForest', { width: 4000 }), TD('precision / recall / F1', { width: 2500 }), TD('0.40 / 0.16 / 0.22', { width: 2860 })]}),
  ], [4000, 2500, 2860]),
  PARA('Numbers shift a little run to run because the source data window slides forward as new GDELT exports get published. Every training run gets appended to metrics/runs.jsonl, and the Models tab of the dashboard plots the trend across runs (Figure 7.7).'),
  H2('10.4 Static reports'),
  PARA('The reports/ directory holds five matplotlib + seaborn figures that pipeline.analysis.generate_all() writes at the end of every pipeline run. We have reproduced them in the Appendix of this document so the report has a self-contained visual record alongside the live dashboard screenshots.'),
];

// ---------- Appendix ----------
const appendix = [
  H1('Appendix A: Static report charts'),
  PARA('The five PNGs below are written by pipeline/analysis.py at the end of every run and also live under reports/. They are deliberately non-interactive: each one captures the state of the warehouse at the moment the pipeline finished, so we can drop them straight into slide decks without worrying about whether the dashboard is up.'),
  H2('A.1 Top-20 locations by mean severity'),
  IMG('country_severity.png', 580, 360),
  CAPTION('Figure A.1: top 20 locations ranked by mean SeverityPct, rendered with seaborn.barplot using the "rocket" palette.'),
  H2('A.2 Tone distribution by CAMEO QuadClass'),
  IMG('tone_by_quadclass.png', 580, 360),
  CAPTION('Figure A.2: violin plot of GDELT AvgTone for each of the four CAMEO QuadClasses. The dashed black line at zero is the neutral-tone reference.'),
  H2('A.3 Global event volume vs mean severity'),
  IMG('volume_timeseries.png', 580, 290),
  CAPTION('Figure A.3: dual-axis matplotlib chart. Blue is events per hour (left axis), orange is mean severity (right axis).'),
  H2('A.4 Feature correlation heatmap'),
  IMG('feature_correlation.png', 480, 360),
  CAPTION('Figure A.4: Pearson correlation between AvgTone, GoldsteinScale, NumSources, NumArticles, NumMentions and the derived SeverityPct.'),
  H2('A.5 Top anomaly locations'),
  IMG('anomaly_breakdown.png', 580, 360),
  CAPTION('Figure A.5: top 15 locations by number of IsolationForest-flagged anomalies in the most recent warehouse window.'),
  H1('Appendix B: Project layout'),
  PARA('The project ships as one directory. Everything needed to reproduce the demo is inside it.'),
  ...CODE_BLOCK(`NYU Big data project/
├── README.md                ← human-readable project guide
├── requirements.txt
├── config.py                ← shared paths + GDELT schema
├── run_pipeline.py          ← CLI orchestrator (8 stages)
├── dashboard.py             ← multi-tab Dash app
├── pipeline/
│   ├── spark_session.py     ← singleton Spark builder (Hive-enabled)
│   ├── ingest.py            ← parallel GDELT download + unzip
│   ├── preprocess.py        ← Spark ETL → partitioned Parquet warehouse
│   ├── classifier.py        ← Spark MLlib RF/LR/DT/SVC + leaderboard
│   ├── deep_severity.py     ← PyTorch FFN + StandardScaler
│   ├── anomaly.py           ← KMeans (Spark) + IsolationForest (sklearn)
│   ├── forecast.py          ← Gradient-boosted hourly tone forecaster
│   ├── analysis.py          ← matplotlib/seaborn static reports
│   └── mlops.py             ← runs.jsonl tracker + run promotion
├── gdelt_data/              ← downloaded 15-min export ZIPs
├── gdelt_data_unzipped/     ← extracted TSVs
├── warehouse/               ← Hive-style partitioned Parquet warehouse
├── dashboard_db/            ← scored events ready for Dash
├── models/                  ← saved Spark / PyTorch / sklearn artefacts
├── metrics/                 ← runs.jsonl, latest.json, pipeline_run.json
├── reports/                 ← matplotlib/seaborn PNGs
└── spark_warehouse/         ← Hive-style metastore root for Spark SQL`),
];

// ============================================================
// DOCUMENT
// ============================================================

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } }, // 11pt body
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Arial', color: '1F3864' },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Arial', color: '111111' },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: '333333' },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets',
        levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: 'numbers',
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({
          text: 'CS-GY 6513 Big Data: Final Project Report',
          size: 18, color: '888888', italics: true,
        })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: 'Page ', size: 18, color: '888888' }),
          new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '888888' }),
          new TextRun({ text: ' of ', size: 18, color: '888888' }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: '888888' }),
        ],
      })] }),
    },
    children: [
      ...titlePage,
      ...tocPage,
      ...executiveSummary,
      ...codeExecution,
      ...architecture,
      ...bigDataConcepts,
      ...challenges,
      ...changes,
      ...uncovered,
      ...lessons,
      ...future,
      ...dataResults,
      ...appendix,
    ],
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(__dirname, 'CS-GY6513_Final_Project_Report.docx');
  fs.writeFileSync(out, buf);
  console.log('wrote', out, '-', buf.length, 'bytes');
});
