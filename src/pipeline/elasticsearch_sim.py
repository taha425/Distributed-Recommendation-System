"""
elasticsearch_sim.py
--------------------
Simulates Elasticsearch querying behavior for product full-text search.

Implements BM25-style ranking (the same algorithm ES uses internally)
to score products against a search query.

In a production system, this module would be replaced with:
  from elasticsearch import Elasticsearch
  es = Elasticsearch(["http://localhost:9200"])
"""

import os
import csv
import json
import math
import re
from collections import defaultdict
from typing import List, Dict, Any

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

# BM25 Parameters (same defaults as Elasticsearch)
BM25_K1 = 1.2
BM25_B  = 0.75


class ElasticsearchSim:
    """
    Simulates an Elasticsearch index over product data.

    Architecture (mirrors real ES):
      - Document store: product_id → {title, category, brand, price, rating}
      - Inverted index: term → {product_id: [positions]}
      - BM25 scoring engine
    """

    def __init__(self):
        self._documents: Dict[int, Dict] = {}       # product_id → doc
        self._inverted_index: Dict[str, Dict[int, int]] = defaultdict(dict)  # term → {pid: tf}
        self._doc_lengths: Dict[int, int] = {}
        self._avg_doc_length: float = 0.0
        self._n_docs: int = 0
        self._indexed: bool = False

    # ── Indexing ──────────────────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple tokenizer: lowercase, split on non-alphanumeric."""
        if not text:
            return []
        return re.findall(r'[a-z0-9]+', text.lower())

    def index_document(self, doc: Dict[str, Any]):
        """Add a single document to the index."""
        pid = int(doc["product_id"])
        self._documents[pid] = doc

        # Combine searchable fields with weights
        text = " ".join([
            str(doc.get("title", ""))    * 3,   # title weight ×3
            str(doc.get("category", "")) * 2,
            str(doc.get("brand", "")),
        ])
        tokens = self._tokenize(text)
        self._doc_lengths[pid] = len(tokens)

        # Build term frequency
        tf = defaultdict(int)
        for token in tokens:
            tf[token] += 1
        for term, freq in tf.items():
            self._inverted_index[term][pid] = freq

    def build_index(self, products_path: str):
        """Index all products from CSV."""
        print("  [ES] Building product index...")
        with open(products_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.index_document(row)

        self._n_docs = len(self._documents)
        total_length = sum(self._doc_lengths.values())
        self._avg_doc_length = total_length / max(self._n_docs, 1)
        self._indexed = True
        print(f"  [ES] Index built: {self._n_docs:,} documents, "
              f"{len(self._inverted_index):,} unique terms")

    # ── BM25 Scoring ─────────────────────────────────────────────────────────

    def _bm25_score(self, term: str, doc_id: int) -> float:
        """Compute BM25 score for a single term-document pair."""
        if term not in self._inverted_index:
            return 0.0
        term_index = self._inverted_index[term]
        if doc_id not in term_index:
            return 0.0

        # IDF component
        df  = len(term_index)
        idf = math.log(1 + (self._n_docs - df + 0.5) / (df + 0.5))

        # TF component with length normalization
        tf  = term_index[doc_id]
        dl  = self._doc_lengths[doc_id]
        avdl = self._avg_doc_length
        tf_norm = (tf * (BM25_K1 + 1)) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * dl / avdl))

        return idf * tf_norm

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 20,
               category_filter: str = None,
               min_rating: float = None) -> List[Dict]:
        """
        Full-text BM25 search with optional filters.

        Returns list of matching products sorted by relevance score.
        """
        if not self._indexed:
            return []

        terms = self._tokenize(query)
        if not terms:
            return []

        # Compute BM25 scores
        scores: Dict[int, float] = defaultdict(float)
        for term in terms:
            if term in self._inverted_index:
                for pid in self._inverted_index[term]:
                    scores[pid] += self._bm25_score(term, pid)

        if not scores:
            return []

        # Apply filters
        results = []
        for pid, score in sorted(scores.items(), key=lambda x: -x[1]):
            doc = self._documents.get(pid, {})
            if category_filter and doc.get("category") != category_filter:
                continue
            if min_rating is not None:
                try:
                    if float(doc.get("avg_rating", 0)) < min_rating:
                        continue
                except (TypeError, ValueError):
                    continue

            results.append({
                "product_id": pid,
                "title":       doc.get("title", ""),
                "category":    doc.get("category", ""),
                "price":       doc.get("price", 0),
                "avg_rating":  doc.get("avg_rating", 0),
                "brand":       doc.get("brand", ""),
                "is_prime":    doc.get("is_prime", False),
                "_score":      round(score, 4),
            })
            if len(results) >= top_k:
                break

        return results

    def get_by_category(self, category: str, top_k: int = 20) -> List[Dict]:
        """Fetch products by category sorted by rating."""
        results = [
            {**doc, "product_id": pid}
            for pid, doc in self._documents.items()
            if doc.get("category") == category
        ]
        results.sort(key=lambda x: -float(x.get("avg_rating", 0) or 0))
        return results[:top_k]

    def get_by_ids(self, product_ids: List[int]) -> List[Dict]:
        """Fetch specific products by ID."""
        return [
            {**self._documents[pid], "product_id": pid}
            for pid in product_ids
            if pid in self._documents
        ]

    def index_stats(self) -> Dict:
        """Return index statistics (mirrors ES /_cat/indices)."""
        return {
            "index_name":      "amazon_products",
            "status":          "green" if self._indexed else "red",
            "n_documents":     self._n_docs,
            "n_unique_terms":  len(self._inverted_index),
            "avg_doc_length":  round(self._avg_doc_length, 1),
            "ranking_algo":    f"BM25 (k1={BM25_K1}, b={BM25_B})",
        }


# ─── Singleton instance ───────────────────────────────────────────────────────
_es_instance: ElasticsearchSim = None


def get_es_instance(products_path: str = None) -> ElasticsearchSim:
    """Get or build the singleton ES index."""
    global _es_instance
    if _es_instance is None or not _es_instance._indexed:
        _es_instance = ElasticsearchSim()
        if products_path is None:
            products_path = os.path.join(RAW_DIR, "amazon_products.csv")
        _es_instance.build_index(products_path)
    return _es_instance


if __name__ == "__main__":
    es = get_es_instance()
    results = es.search("wireless headphones")
    print(json.dumps(results[:3], indent=2))
    print(es.index_stats())
