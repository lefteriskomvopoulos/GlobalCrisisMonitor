"""Spark ETL: parse raw GDELT TSVs into a cleaned, partitioned warehouse table.

Mirrors the Hive workflow described in the proposal: data is read from
the raw file landing zone, projected to the analytics schema, and written
to a date/country partitioned Parquet table that Spark SQL can query
exactly the way Hive would.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from config import GDELT_COLUMNS, UNZIPPED_DIR, WAREHOUSE_DIR
from pipeline.spark_session import get_spark


def _raw_schema() -> T.StructType:
    return T.StructType([T.StructField(c, T.StringType(), True) for c in GDELT_COLUMNS])


def load_raw(spark: SparkSession) -> DataFrame:
    return spark.read.option("sep", "\t").csv(
        f"{UNZIPPED_DIR}/*.CSV", schema=_raw_schema()
    )


def clean(raw: DataFrame) -> DataFrame:
    """Project + cast the raw TSV to the analytics schema, drop bad rows."""
    df = raw.select(
        F.col("GlobalEventID"),
        F.expr("try_cast(trim(QuadClass) as int)").alias("QuadClass"),
        F.col("EventCode"),
        F.col("EventRootCode"),
        F.expr("try_cast(trim(AvgTone) as float)").alias("AvgTone"),
        F.expr("try_cast(trim(GoldsteinScale) as float)").alias("GoldsteinScale"),
        F.expr("try_cast(trim(NumSources) as float)").alias("NumSources"),
        F.expr("try_cast(trim(NumArticles) as float)").alias("NumArticles"),
        F.expr("try_cast(trim(NumMentions) as float)").alias("NumMentions"),
        F.col("Actor1Name"),
        F.col("Actor1CountryCode"),
        F.col("Actor1Type1Code"),
        F.col("Actor2Name"),
        F.col("Actor2CountryCode"),
        F.col("ActionGeo_Fullname").alias("CountryName"),
        F.col("ActionGeo_CountryCode"),
        F.expr("try_cast(trim(ActionGeo_Lat) as double)").alias("ActionGeo_Lat"),
        F.expr("try_cast(trim(ActionGeo_Long) as double)").alias("ActionGeo_Long"),
        F.to_timestamp(F.col("DATEADDED"), "yyyyMMddHHmmss").alias("DateFormatted"),
        F.col("SOURCEURL"),
    ).filter(
        "ActionGeo_Lat IS NOT NULL AND ActionGeo_Long IS NOT NULL "
        "AND QuadClass IS NOT NULL AND AvgTone IS NOT NULL "
        "AND GoldsteinScale IS NOT NULL"
    )

    df = df.withColumn("PartitionDate", F.to_date("DateFormatted"))
    df = df.withColumn(
        "PartitionCountry",
        F.coalesce(F.col("ActionGeo_CountryCode"), F.lit("UNK"))
    )
    return df


def write_warehouse(df: DataFrame) -> int:
    """Write cleaned events to the partitioned warehouse table.

    Partitioned by date + country (Hive-style) so downstream queries can
    push partition filters and avoid full scans.
    """
    n = df.count()
    (df.write
       .mode("overwrite")
       .partitionBy("PartitionDate", "PartitionCountry")
       .parquet(str(WAREHOUSE_DIR)))
    return n


def register_table(spark: SparkSession) -> None:
    """Expose the warehouse as the SQL table ``gdelt_events``.

    Uses the DataFrame source path, which auto-discovers the
    date+country Parquet partitions written by :func:`write_warehouse`.
    """
    spark.read.parquet(str(WAREHOUSE_DIR)).createOrReplaceTempView("gdelt_events")


def run() -> dict:
    spark = get_spark("CrisisMonitor-ETL")
    print("[etl] reading raw TSVs...")
    raw = load_raw(spark)
    print("[etl] cleaning + projecting...")
    cleaned = clean(raw).cache()
    print("[etl] writing partitioned warehouse...")
    n = write_warehouse(cleaned)
    register_table(spark)

    wh = spark.read.parquet(str(WAREHOUSE_DIR))
    distinct_dates = wh.select("PartitionDate").distinct().count()
    distinct_countries = wh.select("PartitionCountry").distinct().count()
    summary = {
        "rows_written": n,
        "partition_dates": distinct_dates,
        "partition_countries": distinct_countries,
    }
    print(f"[etl] done: {summary}")
    cleaned.unpersist()
    return summary


if __name__ == "__main__":
    run()
