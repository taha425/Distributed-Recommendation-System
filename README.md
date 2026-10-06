# Distributed Recommendation System with Clickstream Analysis

## Big Data Analysis — Mini Project

A production-style distributed recommendation engine built with **Apache Spark MLlib**, **GraphX-style graph analytics**, **Elasticsearch-simulated search**, and **Redis-simulated caching** — presented through a full-stack interactive dashboard.

---

## 📋 Project Overview

| Component | Technology |
|---|---|
| Distributed Processing | PySpark (local/cluster mode) |
| Collaborative Filtering | MLlib ALS (Matrix Factorization) |
| Graph Analysis | NetworkX (GraphX-equivalent) |
| Search Layer | Elasticsearch-simulated (BM25 ranking) |
| Caching | Redis-simulated LRU cache |
| API | Flask REST API |
| Dashboard | HTML5 + Vanilla CSS + JS |

## 📦 Datasets

- **Amazon Product Reviews** (UCSD schema) — 100K users, 50K products, 5M interactions (synthetic)
- **Instacart Market Basket Analysis** (Kaggle schema) — 3M order records (synthetic)

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the full pipeline
```bash
python run_pipeline.py
```

### 3. Start the API + dashboard server
```bash
python src/api/app.py
```

### 4. Open dashboard
Navigate to: **http://localhost:5000**

---

## 🗂️ Project Structure

```
bda_mini_proj/
├── data/
│   ├── raw/                    # Synthetic generated datasets (CSV)
│   └── processed/              # Spark pipeline outputs (Parquet/JSON)
├── src/
│   ├── data_generation/
│   │   └── generate_datasets.py     # Generates Amazon + Instacart-style data
│   ├── pipeline/
│   │   ├── clickstream_processor.py # PySpark ETL for clickstream events
│   │   ├── als_recommender.py       # MLlib ALS collaborative filtering
│   │   ├── graph_analysis.py        # Co-purchase graph & PageRank
│   │   ├── elasticsearch_sim.py     # Simulated ES full-text search
│   │   └── redis_cache.py           # Simulated Redis LRU cache
│   └── api/
│       └── app.py                   # Flask REST API
├── dashboard/
│   ├── index.html              # Interactive dashboard UI
│   ├── style.css               # Premium dark design system
│   └── app.js                  # Dashboard logic + Chart.js
├── notebooks/
│   └── analysis.ipynb          # EDA + model evaluation notebook
├── requirements.txt
├── run_pipeline.py             # One-click pipeline orchestrator
└── README.md
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/recommend/<user_id>` | Top-N personalized recommendations |
| GET | `/trending` | Trending products from clickstream |
| GET | `/search?q=<query>` | ES-simulated product search |
| GET | `/graph-stats` | Co-purchase graph analytics |
| GET | `/pipeline-stats` | Full pipeline summary metrics |
| GET | `/user-activity/<user_id>` | User clickstream history |

---

## 🧠 Algorithm Details

### ALS (Alternating Least Squares)
- **Rank**: 50 latent factors
- **Max Iterations**: 20
- **RegParam**: 0.1
- **Implicit Feedback**: Yes (from view/purchase events)

### Graph Analytics
- **Co-purchase Graph**: Products as nodes, co-purchases as weighted edges
- **PageRank**: Identifies authoritative/popular products
- **Community Detection**: Louvain-style clustering of product categories

---

## 📊 Results

After running `run_pipeline.py`, check `data/processed/` for:
- `recommendations.parquet` — ALS model output
- `clickstream_stats.json` — ETL aggregations
- `graph_metrics.json` — PageRank scores & communities
- `model_metrics.json` — RMSE, coverage, novelty
