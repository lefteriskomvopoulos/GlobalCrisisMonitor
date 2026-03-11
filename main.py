import os
import requests
import datetime
import zipfile
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.classification import RandomForestClassifier
from pyspark.sql import types as T
from pyspark.sql import functions as F

# --- 1. ENVIRONMENT SETUP ---
### Ensure you update the JAVA_HOME and HADOOP_HOME paths to match your local system.
os.environ["JAVA_HOME"] = r"C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot"
os.environ["HADOOP_HOME"] = r"C:\hadoop"
java_bin = os.path.join(os.environ["JAVA_HOME"], "bin")
hadoop_bin = os.path.join(os.environ["HADOOP_HOME"], "bin")
os.environ["PATH"] = f"{java_bin};{hadoop_bin};" + os.environ["PATH"]

### Initialize Spark Session with optimized settings for local development
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

# --- 2. FAST DOWNLOAD & UNZIP ---
print("Step 1: Syncing GDELT...")
MASTER_LIST_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
lines = requests.get(MASTER_LIST_URL).text.splitlines()
cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=DAYS_BACK)).strftime("%Y%m%d")
urls = [l.split(" ")[2] for l in lines if "export.CSV.zip" in l and l.split(" ")[2].split("/")[-1][:8] >= cutoff_date]

for url in urls[:2]: 
    file_name = url.split("/")[-1]
    path = os.path.join(DOWNLOAD_DIR, file_name)
    if not os.path.exists(path):
        r = requests.get(url, timeout=10)
        with open(path, "wb") as f: f.write(r.content)
    with zipfile.ZipFile(path, 'r') as zip_ref:
        zip_ref.extractall(UNZIPPED_DIR)

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

# --- 4. LOADING & CLEANING (WITH NULL ISLAND FILTER) ---
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
    F.to_timestamp(F.col("DATEADDED"), "yyyyMMddHHmmss").alias("DateFormatted")
).filter("ActionGeo_Lat IS NOT NULL AND ActionGeo_Long IS NOT NULL")

print(f"📊 Valid rows found: {df.count()}")

### Check the range of Longitude found in the data
df.select(F.min("ActionGeo_Long"), F.max("ActionGeo_Long")).show()

# --- 5. ML PIPELINE ---
train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)
assembler = VectorAssembler(inputCols=["AvgTone", "GoldsteinScale", "NumSources", "NumArticles"], outputCol="features", handleInvalid="skip")
rf = RandomForestClassifier(labelCol="QuadClass", featuresCol="features", numTrees=20, maxDepth=5)
pipeline = Pipeline(stages=[assembler, rf])
model = pipeline.fit(train_df)

# --- 6. SCORING & PERCENTAGE LOGIC ---
print("Step 4: Normalizing Severity to Percentage...")
predictions = model.transform(df)

mm_stats = predictions.select(
    F.min(F.abs("AvgTone")).alias("min_v"), 
    F.max(F.abs("AvgTone")).alias("max_v")
).collect()[0]

min_val = mm_stats['min_v'] if mm_stats['min_v'] else 0
max_val = mm_stats['max_v'] if mm_stats['max_v'] else 1

### Create the SeverityPct column (0-100)
predictions = predictions.withColumn(
    "SeverityPct", 
    F.round(((F.abs(F.col("AvgTone")) - min_val) / (max_val - min_val + 0.0001)) * 100, 1)
)

# --- STEP 7: Export ---
predictions.select(
    "DateFormatted",
    "ActionGeo_Lat", 
    "ActionGeo_Long", 
    "SeverityPct", 
    "CountryName"
).write.mode("overwrite").parquet("dashboard_db")