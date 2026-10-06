"""
clickstream_processor.py
------------------------
PySpark ETL pipeline for processing user clickstream events.

Reads: data/raw/amazon_reviews.csv
Writes: data/processed/clickstream_stats.json
        data/processed/user_product_matrix.parquet
        data/processed/top_products.json
"""

import os
import json
import time
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, IntegerType, StringType,
    FloatType, LongType, TimestampType
)

BASE_DIR      = os.path.join(os.path.dirname(__file__), "..", "..", "data")
RAW_DIR       = os.path.join(BASE_DIR, "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")


def get_spark() -> SparkSession:
    """Create a local Spark session optimized for a development machine."""
    return (
        SparkSession.builder
        .appName("ClickstreamProcessor")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.executor.memory", "4g")
        .config("spark.sql.shuffle.partitions", "50")
        .config("spark.default.parallelism", "8")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )


REVIEWS_SCHEMA = StructType([
    StructField("review_id",    LongType(),   True),
    StructField("user_id",      IntegerType(),True),
    StructField("product_id",   IntegerType(),True),
    StructField("rating",       FloatType(),  True),
    StructField("event_type",   StringType(), True),
    StructField("timestamp",    LongType(),   True),
    StructField("session_id",   StringType(), True),
    StructField("dwell_seconds",IntegerType(),True),
])


def load_reviews(spark: SparkSession):
    path = os.path.join(RAW_DIR, "amazon_reviews.csv")
    print(f"  Loading reviews from {path} …")
    df = (
        spark.read
        .option("header", "true")
        .schema(REVIEWS_SCHEMA)
        .csv(path)
    )
    df = df.withColumn("event_ts", F.to_timestamp(F.col("timestamp").cast("string").cast(LongType()).cast("timestamp")))
    df = df.withColumn("hour",      F.hour(F.col("event_ts")))
    df = df.withColumn("day_of_week", F.dayofweek(F.col("event_ts")))
    return df


def compute_event_distribution(df):
    """Count events by type."""
    return (
        df.groupBy("event_type")
          .count()
          .orderBy(F.desc("count"))
          .collect()
    )


def compute_hourly_activity(df):
    """Events per hour of day."""
    return (
        df.groupBy("hour")
          .count()
          .orderBy("hour")
          .collect()
    )


def compute_top_products(df, n=100):
    """Top products by total interaction count and purchase count."""
    return (
        df.groupBy("product_id")
          .agg(
              F.count("*").alias("total_interactions"),
              F.sum(F.when(F.col("event_type") == "purchase", 1).otherwise(0)).alias("purchase_count"),
              F.sum(F.when(F.col("event_type") == "view",    1).otherwise(0)).alias("view_count"),
              F.avg(F.when(F.col("rating").isNotNull(), F.col("rating"))).alias("avg_rating"),
          )
          .orderBy(F.desc("total_interactions"))
          .limit(n)
    )


def compute_user_activity(df):
    """Per-user activity summary."""
    return (
        df.groupBy("user_id")
          .agg(
              F.count("*").alias("total_events"),
              F.countDistinct("product_id").alias("unique_products_viewed"),
              F.countDistinct("session_id").alias("total_sessions"),
              F.sum(F.when(F.col("event_type") == "purchase", 1).otherwise(0)).alias("purchases"),
              F.avg("dwell_seconds").alias("avg_dwell_seconds"),
          )
    )


def compute_conversion_funnel(df):
    """Funnel: view → add_to_cart → purchase per session."""
    session_events = (
        df.groupBy("session_id")
          .agg(
              F.sum(F.when(F.col("event_type") == "view",         1).otherwise(0)).alias("views"),
              F.sum(F.when(F.col("event_type") == "add_to_cart",  1).otherwise(0)).alias("add_to_carts"),
              F.sum(F.when(F.col("event_type") == "purchase",     1).otherwise(0)).alias("purchases"),
          )
    )
    total_sessions = session_events.count()
    sessions_with_cart     = session_events.filter(F.col("add_to_carts") > 0).count()
    sessions_with_purchase = session_events.filter(F.col("purchases")    > 0).count()

    return {
        "total_sessions":          total_sessions,
        "sessions_with_add_to_cart": sessions_with_cart,
        "sessions_with_purchase":  sessions_with_purchase,
        "cart_add_rate_pct":       round(sessions_with_cart     / total_sessions * 100, 2),
        "conversion_rate_pct":     round(sessions_with_purchase / total_sessions * 100, 2),
    }


def build_interaction_matrix(df):
    """
    Build user-product implicit interaction matrix for ALS.
    Weights: purchase=5, add_to_cart=3, review=4, wishlist=2, view=1
    """
    weight_expr = (
        F.when(F.col("event_type") == "purchase",    5)
         .when(F.col("event_type") == "review",      4)
         .when(F.col("event_type") == "add_to_cart", 3)
         .when(F.col("event_type") == "wishlist",    2)
         .otherwise(1)
    )
    return (
        df.withColumn("weight", weight_expr)
          .groupBy("user_id", "product_id")
          .agg(F.sum("weight").alias("interaction_score"))
          .filter(F.col("interaction_score") > 0)
    )


def run(spark: SparkSession):
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    print("\n[Clickstream Processor] Starting …")
    t0 = time.time()

    df = load_reviews(spark)
    total_events = df.count()
    print(f"  Total events loaded: {total_events:,}")

    # ── Event Distribution ───────────────────────────────────────
    print("  Computing event distribution …")
    event_dist = compute_event_distribution(df)
    event_dist_dict = {row["event_type"]: int(row["count"]) for row in event_dist}

    # ── Hourly Activity ──────────────────────────────────────────
    print("  Computing hourly activity …")
    hourly = compute_hourly_activity(df)
    hourly_dict = {int(row["hour"]): int(row["count"]) for row in hourly}

    # ── Top Products ─────────────────────────────────────────────
    print("  Computing top products …")
    top_products_df = compute_top_products(df, 200)
    top_products_list = [
        {
            "product_id":         int(row["product_id"]),
            "total_interactions": int(row["total_interactions"]),
            "purchase_count":     int(row["purchase_count"]),
            "view_count":         int(row["view_count"]),
            "avg_rating":         round(float(row["avg_rating"]) if row["avg_rating"] else 0, 2),
        }
        for row in top_products_df.collect()
    ]
    try:
        top_products_df.write.mode("overwrite").parquet(
            os.path.join(PROCESSED_DIR, "top_products.parquet")
        )
    except Exception as e:
        print("  ℹ (Hadoop winutils fallback: saving top_products as JSON)")
        with open(os.path.join(PROCESSED_DIR, "top_products.json"), "w") as f:
            json.dump(top_products_list, f, indent=2)

    # ── Conversion Funnel ────────────────────────────────────────
    print("  Computing conversion funnel …")
    funnel = compute_conversion_funnel(df)

    # ── Interaction Matrix ───────────────────────────────────────
    print("  Building user-product interaction matrix …")
    matrix_df = build_interaction_matrix(df)
    matrix_path_parquet = os.path.join(PROCESSED_DIR, "user_product_matrix.parquet")
    matrix_path_csv     = os.path.join(PROCESSED_DIR, "user_product_matrix.csv")

    try:
        matrix_df.write.mode("overwrite").parquet(matrix_path_parquet)
    except Exception:
        print("  ℹ (Hadoop winutils fallback: saving user_product_matrix as CSV)")
        pdf = matrix_df.toPandas()
        pdf.to_csv(matrix_path_csv, index=False)

    matrix_size = matrix_df.count()
    print(f"  Matrix size: {matrix_size:,} user-product pairs")

    # ── User Activity ────────────────────────────────────────────
    print("  Computing user activity stats …")
    user_activity_df = compute_user_activity(df)
    try:
        user_activity_df.write.mode("overwrite").parquet(
            os.path.join(PROCESSED_DIR, "user_activity.parquet")
        )
    except Exception:
        print("  ℹ (Hadoop winutils fallback: user_activity.parquet skipped)")

    # ── Summary Stats ────────────────────────────────────────────
    elapsed = time.time() - t0
    stats = {
        "total_events":         total_events,
        "matrix_size":          matrix_size,
        "event_distribution":   event_dist_dict,
        "hourly_activity":      hourly_dict,
        "top_products":         top_products_list[:50],
        "conversion_funnel":    funnel,
        "processing_time_sec":  round(elapsed, 1),
    }
    stats_path = os.path.join(PROCESSED_DIR, "clickstream_stats.json")
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n  ✓ Clickstream processing complete in {elapsed:.1f}s")
    print(f"  ✓ Stats saved → {stats_path}")
    return stats


if __name__ == "__main__":
    spark = get_spark()
    try:
        run(spark)
    finally:
        spark.stop()
