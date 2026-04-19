"""Centralized Spark session builder with Hive-style warehouse support."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from pyspark.sql import SparkSession

from config import SPARK_WAREHOUSE


def _ensure_java_home() -> None:
    if os.environ.get("JAVA_HOME"):
        return
    try:
        java_home = subprocess.check_output(
            ["/usr/libexec/java_home"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        os.environ["JAVA_HOME"] = java_home
    except Exception:
        pass


def _pin_pyspark_python() -> None:
    """Force Python workers to use the same interpreter as the driver.

    Without this, Spark launches workers with whatever `python3` resolves
    to on PATH, which on macOS can be a different minor version than the
    venv — triggering PYTHON_VERSION_MISMATCH inside Python UDFs.
    """
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)


_session: Optional[SparkSession] = None


def get_spark(app_name: str = "CrisisMonitor") -> SparkSession:
    """Return a singleton Spark session configured with a local warehouse.

    Spark SQL is used in lieu of a full Hive metastore — partitioned tables
    are written to ``spark_warehouse/`` and registered in the in-process
    catalog, so queries work the same way as they would against Hive.
    """
    global _session
    if _session is not None:
        return _session

    _ensure_java_home()
    _pin_pyspark_python()
    _session = (
        SparkSession.builder
        .master("local[*]")
        .appName(app_name)
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.memory", "4g")
        .config("spark.executor.memory", "4g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.warehouse.dir", str(SPARK_WAREHOUSE))
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")
        .config("spark.ui.showConsoleProgress", "false")
        .enableHiveSupport()
        .getOrCreate()
    )
    _session.sparkContext.setLogLevel("ERROR")
    return _session


def stop_spark() -> None:
    global _session
    if _session is not None:
        _session.stop()
        _session = None
