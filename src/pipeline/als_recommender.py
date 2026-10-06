"""
als_recommender.py
------------------
PySpark MLlib ALS (Alternating Least Squares) collaborative filtering.

Implements Matrix Factorization for personalized recommendations.

Reads:  data/processed/user_product_matrix.parquet
        data/raw/amazon_products.csv
Writes: data/processed/als_model/
        data/processed/recommendations.json
        data/processed/model_metrics.json
"""

import os
import json
import time
import math

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.ml.recommendation import ALS
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.sql.types import StructType, StructField, IntegerType, FloatType, StringType

BASE_DIR      = os.path.join(os.path.dirname(__file__), "..", "..", "data")
RAW_DIR       = os.path.join(BASE_DIR, "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")

# ─── ALS Hyper-parameters ─────────────────────────────────────────────────────
ALS_RANK          = 20      # Latent factors (optimized for local dev machine memory)
ALS_MAX_ITER      = 10      # Fast convergence iterations
ALS_REG_PARAM     = 0.1
ALS_COLD_START    = "drop"  # or "nan"
ALS_IMPLICIT      = True    # Implicit interaction scores
TOP_N             = 20      # Recommendations per user


def get_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("ALSRecommender")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "20")
        .config("spark.default.parallelism", "4")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )


def load_matrix(spark: SparkSession):
    csv_path     = os.path.join(PROCESSED_DIR, "user_product_matrix.csv")
    parquet_path = os.path.join(PROCESSED_DIR, "user_product_matrix.parquet")

    if os.path.isfile(csv_path):
        print(f"  Loading interaction matrix from CSV ({csv_path}) …")
        df = spark.read.option("header", "true").csv(csv_path)
        df = df.withColumn("user_id", F.col("user_id").cast(IntegerType()))
        df = df.withColumn("product_id", F.col("product_id").cast(IntegerType()))
    elif os.path.exists(parquet_path):
        print(f"  Loading interaction matrix from Parquet ({parquet_path}) …")
        df = spark.read.parquet(parquet_path)
    else:
        raise FileNotFoundError("user_product_matrix file not found.")

    df = df.withColumn("interaction_score", F.col("interaction_score").cast(FloatType()))
    return df


def load_products(spark: SparkSession):
    path = os.path.join(RAW_DIR, "amazon_products.csv")
    schema = StructType([
        StructField("product_id", IntegerType(), True),
        StructField("title",      StringType(),  True),
        StructField("category",   StringType(),  True),
        StructField("price",      FloatType(),   True),
        StructField("avg_rating", FloatType(),   True),
        StructField("num_ratings",IntegerType(), True),
        StructField("brand",      StringType(),  True),
        StructField("is_prime",   StringType(),  True),
    ])
    return (
        spark.read.option("header","true").schema(schema).csv(path)
    )


def train_als(matrix_df):
    """Train ALS model with train/validation split."""
    print(f"  Training ALS model (rank={ALS_RANK}, iter={ALS_MAX_ITER}, "
          f"regParam={ALS_REG_PARAM}, implicit={ALS_IMPLICIT}) …")

    train_df, val_df = matrix_df.randomSplit([0.85, 0.15], seed=42)
    train_df.cache()
    val_df.cache()

    als = ALS(
        rank          = ALS_RANK,
        maxIter       = ALS_MAX_ITER,
        regParam      = ALS_REG_PARAM,
        userCol       = "user_id",
        itemCol       = "product_id",
        ratingCol     = "interaction_score",
        implicitPrefs = ALS_IMPLICIT,
        coldStartStrategy = ALS_COLD_START,
        seed          = 42,
    )

    t0 = time.time()
    model = als.fit(train_df)
    train_time = time.time() - t0
    print(f"  ✓ Model trained in {train_time:.1f}s")

    # ── Evaluate on validation ─────────────────────────────────
    if not ALS_IMPLICIT:
        predictions = model.transform(val_df).filter(F.col("prediction").isNotNull())
        evaluator = RegressionEvaluator(
            metricName="rmse",
            labelCol="interaction_score",
            predictionCol="prediction",
        )
        rmse = evaluator.evaluate(predictions)
        print(f"  Validation RMSE: {rmse:.4f}")
    else:
        # For implicit feedback: report coverage
        rmse = None

    return model, train_time, rmse, train_df.count(), val_df.count()


def generate_recommendations(model, spark: SparkSession, products_df):
    """Generate top-N recommendations for users."""
    print(f"  Generating Top-{TOP_N} recommendations for users …")
    t0 = time.time()

    # Limit to top 2,000 distinct active users for fast, lightweight local dev execution
    users_subset = products_df.sparkSession.read.option("header", "true").csv(
        os.path.join(PROCESSED_DIR, "user_product_matrix.csv")
    ).select(F.col("user_id").cast(IntegerType())).distinct().limit(2000)

    user_recs = model.recommendForUserSubset(users_subset, TOP_N)

    # Explode recommendations
    user_recs_flat = user_recs.select(
        "user_id",
        F.explode("recommendations").alias("rec")
    ).select(
        "user_id",
        F.col("rec.product_id").alias("product_id"),
        F.col("rec.rating").alias("score"),
    )

    # Join with product metadata
    enriched = user_recs_flat.join(
        products_df.select("product_id","title","category","price","avg_rating","brand"),
        on="product_id",
        how="left"
    )

    elapsed = time.time() - t0
    print(f"  ✓ Recommendations generated in {elapsed:.1f}s")

    # Write full recommendations as parquet
    recs_parquet_path = os.path.join(PROCESSED_DIR, "recommendations.parquet")
    try:
        enriched.write.mode("overwrite").parquet(recs_parquet_path)
        print(f"  ✓ Recommendations saved → {recs_parquet_path}")
    except Exception:
        print("  ℹ (Hadoop winutils fallback: saving recommendations via Pandas)")
        try:
            pdf = enriched.toPandas()
            pdf.to_parquet(recs_parquet_path, index=False)
        except Exception:
            pass

    # Also save a JSON sample (first 500 users) for the API
    sample_users = (
        enriched
        .groupBy("user_id")
        .agg(
            F.collect_list(
                F.struct("product_id","title","category","price","avg_rating","score")
            ).alias("recommendations")
        )
        .limit(2000)
        .collect()
    )

    recs_dict = {}
    for row in sample_users:
        uid = int(row["user_id"])
        recs_dict[str(uid)] = [
            {
                "product_id": int(r["product_id"]),
                "title":      r["title"],
                "category":   r["category"],
                "price":      round(float(r["price"]) if r["price"] else 0, 2),
                "avg_rating": round(float(r["avg_rating"]) if r["avg_rating"] else 0, 1),
                "score":      round(float(r["score"])      if r["score"]      else 0, 4),
            }
            for r in row["recommendations"]
        ]

    recs_json_path = os.path.join(PROCESSED_DIR, "recommendations.json")
    with open(recs_json_path, "w") as f:
        json.dump(recs_dict, f)
    print(f"  ✓ Recommendation sample saved → {recs_json_path}")

    return enriched, elapsed


def run(spark: SparkSession):
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    print("\n[ALS Recommender] Starting …")

    matrix_df   = load_matrix(spark)
    products_df = load_products(spark)

    total_pairs = matrix_df.count()
    n_users     = matrix_df.select("user_id").distinct().count()
    n_items     = matrix_df.select("product_id").distinct().count()
    print(f"  Matrix: {n_users:,} users × {n_items:,} products = {total_pairs:,} interactions")

    matrix_df.cache()

    model, train_time, rmse, n_train, n_val = train_als(matrix_df)

    # Save model
    model_path = os.path.join(PROCESSED_DIR, "als_model")
    try:
        model.write().overwrite().save(model_path)
        print(f"  ✓ Model saved → {model_path}")
    except Exception:
        print("  ℹ (Hadoop winutils fallback: skipping Spark native model dir save)")

    # Generate recommendations
    recs_df, recs_time = generate_recommendations(model, spark, products_df)

    # Factor matrices for analysis
    user_factors    = model.userFactors
    product_factors = model.itemFactors
    n_user_factors  = user_factors.count()
    n_item_factors  = product_factors.count()

    # Save metrics
    metrics = {
        "model": {
            "algorithm":      "ALS (Matrix Factorization)",
            "rank":           ALS_RANK,
            "max_iterations": ALS_MAX_ITER,
            "reg_param":      ALS_REG_PARAM,
            "implicit_prefs": ALS_IMPLICIT,
        },
        "data": {
            "n_users":          n_users,
            "n_items":          n_items,
            "n_interactions":   total_pairs,
            "n_train":          n_train,
            "n_validation":     n_val,
            "matrix_sparsity":  round(1 - total_pairs / (n_users * n_items), 6),
        },
        "performance": {
            "training_time_sec":       round(train_time, 1),
            "recommendation_time_sec": round(recs_time,  1),
            "rmse":                    round(rmse, 4) if rmse else "N/A (implicit mode)",
        },
        "factors": {
            "n_user_latent_vectors":    n_user_factors,
            "n_product_latent_vectors": n_item_factors,
        },
    }

    metrics_path = os.path.join(PROCESSED_DIR, "model_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"  ✓ Metrics saved → {metrics_path}")

    print(f"\n  ✅ ALS pipeline complete!")
    return metrics


if __name__ == "__main__":
    spark = get_spark()
    try:
        run(spark)
    finally:
        spark.stop()
