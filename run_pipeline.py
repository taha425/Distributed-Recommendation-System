"""
run_pipeline.py
---------------
One-click pipeline orchestrator for the BDA mini project.

Runs in order:
  1. Data Generation  (Amazon + Instacart synthetic datasets)
  2. Clickstream ETL  (PySpark)
  3. ALS Recommender  (PySpark MLlib)
  4. Graph Analysis   (NetworkX / GraphX-style)

Usage:
  python run_pipeline.py
  python run_pipeline.py --skip-data    (skip data generation)
  python run_pipeline.py --only-graph   (only graph analysis)
"""

import sys
import os
import time
import json
import argparse

# ─── CLI Arguments ────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="BDA Mini Project Pipeline Runner")
parser.add_argument("--skip-data",     action="store_true", help="Skip data generation (use existing)")
parser.add_argument("--skip-spark",    action="store_true", help="Skip Spark pipeline steps")
parser.add_argument("--only-graph",    action="store_true", help="Run only graph analysis")
parser.add_argument("--only-recs",     action="store_true", help="Run only ALS recommender")
args = parser.parse_args()

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "data", "processed")
RAW_DIR       = os.path.join(os.path.dirname(__file__), "data", "raw")


def banner(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def step(n: int, title: str):
    print("\n" + "-" * 60)
    print(f"  STEP {n}: {title}")
    print("-" * 60)


def check_raw_data() -> bool:
    """Check if raw data already exists."""
    required = ["amazon_products.csv", "amazon_reviews.csv",
                "instacart_orders.csv", "instacart_order_products.csv"]
    return all(os.path.exists(os.path.join(RAW_DIR, f)) for f in required)


def main():
    banner("Distributed Recommendation System - Pipeline Runner")
    t_total = time.time()

    pipeline_summary = {
        "stages": {},
        "total_time_sec": 0,
    }

    # ── Step 1: Data Generation ───────────────────────────────────────────────
    if not args.skip_data and not args.only_graph and not args.only_recs:
        step(1, "Data Generation (Amazon + Instacart Synthetic)")

        if check_raw_data():
            print("  Info: Raw data already exists. Skipping generation.")
            print("  (Delete data/raw/ to regenerate)")
        else:
            t0 = time.time()
            from src.data_generation.generate_datasets import main as gen_main
            gen_main()
            elapsed = time.time() - t0
            pipeline_summary["stages"]["data_generation"] = {
                "status": "completed",
                "time_sec": round(elapsed, 1),
            }
    else:
        print("\n  Info: Skipping data generation (--skip-data flag or selective run)")
        if not check_raw_data():
            print("\n  ERROR: Raw data not found! Run without --skip-data first.")
            sys.exit(1)

    # ── Step 2: Clickstream ETL ───────────────────────────────────────────────
    if not args.skip_spark and not args.only_graph and not args.only_recs:
        step(2, "Clickstream ETL (PySpark)")
        t0 = time.time()
        from pyspark.sql import SparkSession
        from src.pipeline.clickstream_processor import get_spark, run as clickstream_run

        spark = get_spark()
        try:
            stats = clickstream_run(spark)
            elapsed = time.time() - t0
            pipeline_summary["stages"]["clickstream_etl"] = {
                "status":      "completed",
                "time_sec":    round(elapsed, 1),
                "total_events": stats.get("total_events", 0),
                "matrix_size":  stats.get("matrix_size", 0),
            }
        finally:
            spark.stop()

    # ── Step 3: ALS Recommender ───────────────────────────────────────────────
    if not args.skip_spark and not args.only_graph:
        step(3, "ALS Collaborative Filtering (PySpark MLlib)")
        t0 = time.time()
        from pyspark.sql import SparkSession
        from src.pipeline.als_recommender import get_spark as als_spark, run as als_run

        spark = als_spark()
        try:
            metrics = als_run(spark)
            elapsed = time.time() - t0
            pipeline_summary["stages"]["als_recommender"] = {
                "status":   "completed",
                "time_sec": round(elapsed, 1),
                "metrics":  metrics,
            }
        finally:
            spark.stop()

    # ── Step 4: Graph Analysis ────────────────────────────────────────────────
    if not args.skip_spark and not args.only_recs:
        step(4, "Graph Analytics (NetworkX / GraphX-equivalent)")
        t0 = time.time()
        from src.pipeline.graph_analysis import run as graph_run

        graph_metrics = graph_run()
        elapsed = time.time() - t0
        pipeline_summary["stages"]["graph_analysis"] = {
            "status":   "completed",
            "time_sec": round(elapsed, 1),
            "graph_stats": graph_metrics.get("graph_stats", {}),
        }

    # ── Pipeline Summary ──────────────────────────────────────────────────────
    total_elapsed = time.time() - t_total
    pipeline_summary["total_time_sec"] = round(total_elapsed, 1)

    banner("Pipeline Complete! [OK]")
    print(f"\n  Total time: {total_elapsed:.1f}s\n")

    for stage, info in pipeline_summary["stages"].items():
        status = "[OK]" if info["status"] == "completed" else "[X]"
        print(f"  {status} {stage:<25} {info['time_sec']}s")

    summary_path = os.path.join(PROCESSED_DIR, "pipeline_summary.json")
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(pipeline_summary, f, indent=2)

    print(f"\n  Results saved in: data/processed/")
    print(f"  Pipeline summary: {summary_path}")
    print(f"\n  -> Start the dashboard: python src/api/app.py")
    print(f"  -> Then open:           http://localhost:5000\n")


if __name__ == "__main__":
    main()
