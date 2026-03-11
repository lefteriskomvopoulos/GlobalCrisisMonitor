import os
import requests
import datetime
import zipfile
import time
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.classification import RandomForestClassifier, LogisticRegression, DecisionTreeClassifier, OneVsRest, LinearSVC
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.clustering import KMeans
from pyspark.sql import types as T
from pyspark.sql import functions as F

# --- 1. ENVIRONMENT SETUP ---
if not os.environ.get("JAVA_HOME"):
    try:
        import subprocess
        java_home = subprocess.check_output(["/usr/libexec/java_home"]).decode("utf-8").strip()
        os.environ["JAVA_HOME"] = java_home
    except Exception:
        pass

try:
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("CrisisMonitor") \
        .config("spark.driver.bindAddress", "127.0.0.1") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .config("spark.sql.shuffle.partitions", "8") \
        .getOrCreate()
    print("✅ SUCCESS: Spark Engine is live!")
except Exception as e:
    print(f"❌ Initialization Error: {e}")
    exit()

DOWNLOAD_DIR = "gdelt_data"
UNZIPPED_DIR = "gdelt_data_unzipped"
DAYS_BACK = 3
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(UNZIPPED_DIR, exist_ok=True)

auto_refresh_timer = 1  # Auto refresh every 30 minutes

# --- ML MODEL SELECTION (PROMPT ONCE) ---
print("\n============= ML MODEL SELECTION =============")
print("Which model would you like to use for event classification?")
print("1. Random Forest Classifier (Default)")
print("2. Logistic Regression")
print("3. Decision Tree Classifier")
print("4. Support Vector Machine (One-vs-Rest)")
choice = input("Enter your choice (1-4): ").strip()

while True:
    print(f"\n--- Starting Pipeline Run at {datetime.datetime.now()} ---")
    
    # --- 2. FAST DOWNLOAD & UNZIP ---
    print("Step 1: Syncing GDELT...")
    MASTER_LIST_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
    try:
        lines = requests.get(MASTER_LIST_URL).text.splitlines()
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=DAYS_BACK)).strftime("%Y%m%d")
        urls = [l.split(" ")[2] for l in lines if "export.CSV.zip" in l and l.split(" ")[2].split("/")[-1][:8] >= cutoff_date]
        
        # INCREASED VOLUME: Download 48 file chunks (approx ~12 hours of global events)
        for url in urls[:48]: 
            file_name = url.split("/")[-1]
            path = os.path.join(DOWNLOAD_DIR, file_name)
            if not os.path.exists(path):
                r = requests.get(url, timeout=10)
                with open(path, "wb") as f: f.write(r.content)
            with zipfile.ZipFile(path, 'r') as zip_ref:
                zip_ref.extractall(UNZIPPED_DIR)
    except Exception as e:
        print(f"Error during download: {e}")

    # --- 3. SCHEMA ---
    col_names = [
        "GlobalEventID", "Day", "MonthYear", "Year", "FractionDate", 
        "Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode", "Actor1EthnicCode", 
        "Actor1Religion1Code", "Actor1Religion2Code", "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code", 
        "Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode", "Actor2EthnicCode", 
        "Actor2Religion1Code", "Actor2Religion2Code", "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code", 
        "IsRootEvent", "EventCode", "EventBaseCode", "EventRootCode", "QuadClass", 
        "GoldsteinScale", "NumMentions", "NumSources", "NumArticles", "AvgTone", 
        "Actor1Geo_Type", "Actor1Geo_Fullname", "Actor1Geo_CountryCode", "Actor1Geo_ADM1Code", "Actor1Geo_ADM2Code", 
        "Actor1Geo_Lat", "Actor1Geo_Long", "Actor1Geo_FeatureID", 
        "Actor2Geo_Type", "Actor2Geo_Fullname", "Actor2Geo_CountryCode", "Actor2Geo_ADM1Code", "Actor2Geo_ADM2Code", 
        "Actor2Geo_Lat", "Actor2Geo_Long", "Actor2Geo_FeatureID", 
        "ActionGeo_Type", "ActionGeo_Fullname", "ActionGeo_CountryCode", "ActionGeo_ADM1Code", "ActionGeo_ADM2Code", 
        "ActionGeo_Lat", "ActionGeo_Long", "ActionGeo_FeatureID",
        "DATEADDED", "SOURCEURL"
    ]
    
    gdelt_schema = T.StructType([T.StructField(c, T.StringType(), True) for c in col_names])
    
    # --- 4. LOADING & CLEANING ---
    print("Step 2: Loading and filtering...")
    raw_df = spark.read.option("sep", "\t").csv(f"{UNZIPPED_DIR}/*.CSV", schema=gdelt_schema)
    
    df = raw_df.select(
        F.expr("try_cast(trim(QuadClass) as int)").alias("QuadClass"),
        F.expr("try_cast(trim(AvgTone) as float)").alias("AvgTone"),
        F.expr("try_cast(trim(GoldsteinScale) as float)").alias("GoldsteinScale"),
        F.expr("try_cast(trim(NumSources) as float)").alias("NumSources"),
        F.expr("try_cast(trim(NumArticles) as float)").alias("NumArticles"),
        F.col("ActionGeo_Fullname").alias("CountryName"),
        F.expr("try_cast(trim(ActionGeo_Lat) as double)").alias("ActionGeo_Lat"),
        F.expr("try_cast(trim(ActionGeo_Long) as double)").alias("ActionGeo_Long"),
        F.to_timestamp(F.col("DATEADDED"), "yyyyMMddHHmmss").alias("DateFormatted"),
        F.col("SOURCEURL")
    ).filter("ActionGeo_Lat IS NOT NULL AND ActionGeo_Long IS NOT NULL")
    
    print(f"📊 Valid rows found: {df.count()}")
    
    # --- 5. ML PIPELINE ---
    if choice == '2':
        model_name = "Logistic Regression"
        ml_model = LogisticRegression(labelCol="QuadClass", featuresCol="features", maxIter=10)
    elif choice == '3':
        model_name = "Decision Tree Classifier"
        ml_model = DecisionTreeClassifier(labelCol="QuadClass", featuresCol="features")
    elif choice == '4':
        model_name = "Support Vector Machine (One-vs-Rest)"
        lsvc = LinearSVC(maxIter=10)
        ml_model = OneVsRest(classifier=lsvc, labelCol="QuadClass", featuresCol="features")
    else:
        model_name = "Random Forest Classifier"
        ml_model = RandomForestClassifier(labelCol="QuadClass", featuresCol="features", numTrees=20, maxDepth=5)
    
    print(f"\n🚀 Initializing {model_name}...")
    train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)
    assembler = VectorAssembler(inputCols=["AvgTone", "GoldsteinScale", "NumSources", "NumArticles"], outputCol="features", handleInvalid="skip")
    
    pipeline = Pipeline(stages=[assembler, ml_model])
    model = pipeline.fit(train_df)
    
    # Evaluate model
    print(f"Step 4: Evaluating {model_name} on active test set...")
    predictions_test = model.transform(test_df)
    
    evaluator_acc = MulticlassClassificationEvaluator(labelCol="QuadClass", predictionCol="prediction", metricName="accuracy")
    evaluator_f1 = MulticlassClassificationEvaluator(labelCol="QuadClass", predictionCol="prediction", metricName="f1")
    
    acc = evaluator_acc.evaluate(predictions_test)
    f1 = evaluator_f1.evaluate(predictions_test)
    
    print(f"📊 Model Accuracy: {acc:.4f}")
    print(f"📊 Model F1 Score:  {f1:.4f}\n")
    
    # --- 6. SCORING & ANOMALY DETECTION ---
    print("Step 5: Running K-Means Anomaly Detection & Normalizing Severity...")
    predictions = model.transform(df)
    
    # Unsupervised Anomaly Detection using K-Means Clustering
    kmeans = KMeans(k=5, seed=42, featuresCol="features", predictionCol="AnomalyCluster")
    model_kmeans = kmeans.fit(predictions)
    predictions = model_kmeans.transform(predictions)
    
    mm_stats = predictions.select(
        F.min(F.abs("AvgTone")).alias("min_v"), 
        F.max(F.abs("AvgTone")).alias("max_v")
    ).collect()[0]
    
    min_val = mm_stats['min_v'] if mm_stats['min_v'] else 0
    max_val = mm_stats['max_v'] if mm_stats['max_v'] else 1
    
    predictions = predictions.withColumn(
        "SeverityPct", 
        F.round(((F.abs(F.col("AvgTone")) - min_val) / (max_val - min_val + 0.0001)) * 100, 1)
    )
    
    # --- STEP 7: Export ---
    print("Step 6: Exporting Partitioned Parquet data for dashboard...")
    predictions = predictions.withColumn("PartitionDate", F.to_date("DateFormatted"))
    
    predictions.select(
        "DateFormatted",
        "PartitionDate",
        "ActionGeo_Lat", 
        "ActionGeo_Long", 
        "SeverityPct", 
        "CountryName",
        "AnomalyCluster",
        "SOURCEURL"
    ).write.mode("overwrite").partitionBy("PartitionDate").parquet("dashboard_db")
    
    print(f"\n✅ Pipeline complete! Sleeping for {auto_refresh_timer} minutes...")
    time.sleep(auto_refresh_timer * 60)