"""Central configuration for the GDELT Crisis Monitor pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DOWNLOAD_DIR = ROOT / "gdelt_data"
UNZIPPED_DIR = ROOT / "gdelt_data_unzipped"
WAREHOUSE_DIR = ROOT / "warehouse"
DASHBOARD_DB = ROOT / "dashboard_db"
MODELS_DIR = ROOT / "models"
METRICS_DIR = ROOT / "metrics"
REPORTS_DIR = ROOT / "reports"
SPARK_WAREHOUSE = ROOT / "spark_warehouse"

for d in (DOWNLOAD_DIR, UNZIPPED_DIR, WAREHOUSE_DIR, DASHBOARD_DB,
          MODELS_DIR, METRICS_DIR, REPORTS_DIR, SPARK_WAREHOUSE):
    d.mkdir(parents=True, exist_ok=True)

GDELT_MASTER_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"

GDELT_COLUMNS = [
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
    "DATEADDED", "SOURCEURL",
]

QUAD_CLASS_LABELS = {
    1: "Verbal Cooperation",
    2: "Material Cooperation",
    3: "Verbal Conflict",
    4: "Material Conflict",
}

FEATURE_COLS = ["AvgTone", "GoldsteinScale", "NumSources", "NumArticles", "NumMentions"]
