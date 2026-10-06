"""
graph_analysis.py
-----------------
Co-purchase graph analytics using NetworkX (equivalent to Spark GraphX).

Builds a bipartite product co-purchase graph, computes PageRank,
finds product communities, and identifies influential product hubs.

Reads:  data/raw/instacart_order_products.csv
        data/raw/instacart_products.csv
Writes: data/processed/graph_metrics.json
        data/processed/product_communities.json
"""

import os
import json
import time
import csv
from collections import defaultdict

import networkx as nx
import numpy as np

BASE_DIR      = os.path.join(os.path.dirname(__file__), "..", "..", "data")
RAW_DIR       = os.path.join(BASE_DIR, "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")

# Limit how many orders we process for graph construction (for speed)
MAX_ORDERS = 500_000


def load_product_names() -> dict:
    """Load product_id → name mapping."""
    path = os.path.join(RAW_DIR, "instacart_products.csv")
    names = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            names[int(row["product_id"])] = row["product_name"]
    return names


def load_order_baskets() -> dict:
    """Load order_id → list of product_ids."""
    path = os.path.join(RAW_DIR, "instacart_order_products.csv")
    baskets = defaultdict(list)
    order_count = 0
    print(f"  Loading order-product data (max {MAX_ORDERS:,} orders) …")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        seen_orders = set()
        for row in reader:
            oid = int(row["order_id"])
            if oid not in seen_orders:
                if len(seen_orders) >= MAX_ORDERS:
                    break
                seen_orders.add(oid)
            baskets[oid].append(int(row["product_id"]))
    print(f"  Loaded {len(baskets):,} baskets")
    return dict(baskets)


def build_copurchase_graph(baskets: dict) -> nx.Graph:
    """
    Build an undirected weighted graph:
      nodes = products
      edges = co-purchase count (products bought together in same order)
    """
    print("  Building co-purchase graph …")
    G = nx.Graph()
    edge_weights = defaultdict(int)

    for basket in baskets.values():
        prods = list(set(basket))
        if len(prods) < 2:
            continue
        # Only consider pairs within baskets of ≤ 15 items to avoid combinatorial explosion
        if len(prods) > 15:
            prods = prods[:15]
        for i in range(len(prods)):
            for j in range(i + 1, len(prods)):
                a, b = min(prods[i], prods[j]), max(prods[i], prods[j])
                edge_weights[(a, b)] += 1

    # Only keep edges with weight ≥ 2 (appeared together at least twice)
    for (a, b), w in edge_weights.items():
        if w >= 2:
            G.add_edge(a, b, weight=w)

    print(f"  Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    return G


def compute_pagerank(G: nx.Graph) -> dict:
    """Compute PageRank scores for all product nodes."""
    print("  Computing PageRank …")
    t0 = time.time()
    # Use personalized PageRank with edge weights
    pr = nx.pagerank(G, alpha=0.85, weight="weight", max_iter=100)
    print(f"  ✓ PageRank done in {time.time()-t0:.1f}s")
    return pr


def detect_communities(G: nx.Graph) -> dict:
    """
    Community detection using Greedy Modularity Maximization
    (approximation of Louvain algorithm).
    Returns: product_id → community_id
    """
    print("  Detecting communities (Greedy Modularity) …")
    t0 = time.time()
    # Work on the largest connected component
    largest_cc = max(nx.connected_components(G), key=len)
    G_sub = G.subgraph(largest_cc).copy()

    communities = nx.community.greedy_modularity_communities(G_sub, weight="weight")
    community_map = {}
    for cid, community in enumerate(communities):
        for node in community:
            community_map[int(node)] = cid

    print(f"  ✓ {len(communities)} communities detected in {time.time()-t0:.1f}s")
    return community_map, len(communities)


def compute_centrality(G: nx.Graph) -> dict:
    """Compute degree centrality and betweenness centrality (sampled)."""
    print("  Computing centrality measures …")
    degree_centrality = nx.degree_centrality(G)
    # Betweenness is expensive; compute on subgraph
    if G.number_of_nodes() > 5000:
        nodes_sample = list(G.nodes())[:5000]
        G_small = G.subgraph(nodes_sample)
    else:
        G_small = G
    betweenness = nx.betweenness_centrality(G_small, weight="weight", normalized=True)
    return degree_centrality, betweenness


def run():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    print("\n[Graph Analysis] Starting …")
    t0 = time.time()

    # ── Load data ─────────────────────────────────────────────
    product_names = load_product_names()
    baskets       = load_order_baskets()

    # ── Build graph ───────────────────────────────────────────
    G = build_copurchase_graph(baskets)

    if G.number_of_nodes() == 0:
        print("  ⚠ Empty graph — skipping analytics")
        return {}

    # ── PageRank ─────────────────────────────────────────────
    pagerank = compute_pagerank(G)

    # ── Communities ──────────────────────────────────────────
    community_map, n_communities = detect_communities(G)

    # ── Centrality ───────────────────────────────────────────
    degree_centrality, betweenness = compute_centrality(G)

    # ── Top PageRank products ─────────────────────────────────
    top_pr = sorted(pagerank.items(), key=lambda x: -x[1])[:100]
    top_pr_list = [
        {
            "product_id":        int(pid),
            "name":              product_names.get(int(pid), f"Product-{pid}"),
            "pagerank":          round(float(score), 8),
            "degree_centrality": round(float(degree_centrality.get(pid, 0)), 6),
            "community_id":      community_map.get(int(pid), -1),
        }
        for pid, score in top_pr
    ]

    # ── Community summary ────────────────────────────────────
    community_sizes = defaultdict(int)
    for cid in community_map.values():
        community_sizes[cid] += 1
    community_summary = [
        {"community_id": k, "size": v}
        for k, v in sorted(community_sizes.items(), key=lambda x: -x[1])[:20]
    ]

    # ── Graph stats ─────────────────────────────────────────
    degrees = [d for _, d in G.degree()]
    elapsed = time.time() - t0

    graph_metrics = {
        "graph_stats": {
            "n_nodes":             G.number_of_nodes(),
            "n_edges":             G.number_of_edges(),
            "avg_degree":          round(float(np.mean(degrees)), 2),
            "max_degree":          int(np.max(degrees)),
            "density":             round(float(nx.density(G)), 6),
            "n_connected_components": int(nx.number_connected_components(G)),
            "n_communities":       n_communities,
        },
        "top_products_by_pagerank": top_pr_list,
        "community_sizes":         community_summary,
        "processing_time_sec":     round(elapsed, 1),
    }

    graph_path = os.path.join(PROCESSED_DIR, "graph_metrics.json")
    with open(graph_path, "w") as f:
        json.dump(graph_metrics, f, indent=2)
    print(f"  ✓ Graph metrics saved → {graph_path}")

    # ── Save community assignments ───────────────────────────
    communities_path = os.path.join(PROCESSED_DIR, "product_communities.json")
    community_output = {
        str(pid): {"community_id": cid,
                   "name": product_names.get(pid, f"Product-{pid}")}
        for pid, cid in community_map.items()
    }
    with open(communities_path, "w") as f:
        json.dump(community_output, f)
    print(f"  ✓ Communities saved → {communities_path}")

    print(f"\n  ✅ Graph analysis complete in {elapsed:.1f}s")
    return graph_metrics


if __name__ == "__main__":
    run()
