"""
generate_datasets.py
--------------------
Generates realistic synthetic datasets mirroring:
  1. Amazon Product Reviews & Metadata (UCSD schema)
  2. Instacart Market Basket Analysis (Kaggle schema)

Scale: 100K users, 50K products, 5M interactions, 3M orders
"""

import os
import random
import json
import csv
import time
from datetime import datetime, timedelta
import numpy as np

# ─── Configuration ────────────────────────────────────────────────────────────
N_USERS       = 100_000
N_PRODUCTS    = 50_000
N_REVIEWS     = 5_000_000
N_ORDERS      = 3_000_000
N_AISLES      = 134
N_DEPARTMENTS = 21
SEED          = 42

random.seed(SEED)
np.random.seed(SEED)

BASE_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

# ─── Amazon Categories & Product Names ────────────────────────────────────────
AMAZON_CATEGORIES = [
    "Electronics", "Books", "Clothing", "Home & Kitchen", "Sports & Outdoors",
    "Beauty & Personal Care", "Toys & Games", "Automotive", "Health & Wellness",
    "Office Products", "Garden & Outdoor", "Pet Supplies", "Music", "Movies & TV",
    "Video Games", "Baby", "Grocery", "Arts & Crafts", "Tools & Hardware", "Jewelry"
]

ADJECTIVES = ["Premium", "Ultra", "Smart", "Pro", "Elite", "Classic", "Advanced",
              "Portable", "Wireless", "Compact", "Deluxe", "Slim", "Heavy-Duty", "Eco"]
NOUNS_ELECTRONICS = ["Headphones", "Speaker", "Tablet", "Charger", "Cable", "Camera",
                     "Keyboard", "Mouse", "Monitor", "Laptop Stand", "USB Hub", "Webcam"]
NOUNS_BOOKS = ["Guide to Python", "Data Science Handbook", "Machine Learning Basics",
               "Big Data Analytics", "Cloud Computing Essentials", "AI for Everyone"]
NOUNS_CLOTHING = ["T-Shirt", "Jacket", "Jeans", "Sneakers", "Hat", "Backpack",
                  "Hoodie", "Shorts", "Dress", "Socks"]
NOUNS_HOME = ["Coffee Maker", "Blender", "Air Fryer", "Instant Pot", "Toaster",
              "Water Filter", "Vacuum Cleaner", "Storage Box", "Lamp", "Mirror"]

CATEGORY_NOUNS = {
    "Electronics": NOUNS_ELECTRONICS, "Books": NOUNS_BOOKS,
    "Clothing": NOUNS_CLOTHING, "Home & Kitchen": NOUNS_HOME,
}
DEFAULT_NOUNS = ["Item", "Product", "Set", "Kit", "Pack", "Bundle", "Collection"]

EVENT_TYPES = ["view", "view", "view", "add_to_cart", "purchase", "wishlist", "search", "review"]

INSTACART_DEPARTMENTS = [
    "produce", "dairy eggs", "snacks", "beverages", "frozen", "bakery",
    "canned goods", "dry goods pasta", "meat seafood", "personal care",
    "household", "babies", "breakfast", "international", "alcohol",
    "pantry", "missing", "bulk", "pets", "deli", "other"
]

INSTACART_AISLES = [
    "fresh fruits", "fresh vegetables", "packaged cheese", "yogurt", "milk",
    "water seltzer sparkling water", "soda", "chips pretzels", "cookies cakes",
    "ice cream ice", "frozen meals", "frozen pizza", "cereal", "bread",
    "pasta rice", "canned tomatoes", "canned beans", "coffee", "tea",
    "energy drinks sports drinks", "juice nectars", "candy chocolate",
    "crackers", "granola bars", "nuts seeds dried fruit", "condiments",
    "oils vinegars", "spices seasonings", "baking ingredients", "soup broth",
    "cleaning products", "laundry", "paper goods", "baby food formula",
    "diapers wipes", "dog food care", "cat food care", "vitamins supplements",
    "hair care", "skin care", "oral hygiene", "feminine care", "shampoo",
    "fresh dips tapenades", "tofu meat alternatives", "hot dogs bacon sausage",
    "lunch meat", "eggs", "butter", "cream", "refrigerated", "frozen breakfast",
    "popcorn jerky", "packaged produce", "salad dressing toppings", "pickles olives",
    "preserved dips spreads", "more breakfast foods", "grains rice dried goods",
    "flour sugar baking", "prepared meals", "prepared soups salads",
    "refrigerated pudding desserts", "frozen juice", "frozen produce",
    "frozen meat seafood", "specialty wines champagnes", "red wines",
    "white wines", "beers coolers", "spirits", "packaged meat",
    "fresh pasta", "fresh herbs", "specialty cheese", "other creams cheeses",
    "kosher foods", "latino foods", "asian foods", "middle eastern foods",
    "instant foods", "dry pasta", "dish detergents", "trash bags liners",
    "air fresheners candles", "baby accessories", "food storage", "kitchen supplies",
    "office supplies", "batteries", "cleaning tools brushes brooms dusters",
    "plates bowls cups flatware", "towels linens", "shower bath", "body lotions",
    "deodorants", "first aid", "cold flu allergy", "digestion", "protein",
    "weight loss", "meal replacement strips", "mint gum", "chips salsas dips",
    "trail mix snack mix", "donuts pastries", "bagels english muffins",
    "pies tarts", "lunch snacks", "snack bars", "energy granola bars",
    "peanut butter jams spreads", "honey syrup", "stuffing sides",
    "stuffing bread crumbs", "soups stews", "artisan breads", "rolls buns",
    "tortillas flat bread", "packaged seafood", "deli meats", "salami",
    "sausages kielbasa", "game meats",
]


def make_product_name(category: str, pid: int) -> str:
    adj  = random.choice(ADJECTIVES)
    nouns = CATEGORY_NOUNS.get(category, DEFAULT_NOUNS)
    noun = random.choice(nouns)
    brand_id = pid % 500 + 1
    return f"{adj} {noun} — Brand-{brand_id:04d}"


def generate_amazon_products(path: str):
    print(f"  Generating {N_PRODUCTS:,} products …")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "title", "category", "price", "avg_rating",
                    "num_ratings", "brand", "is_prime"])
        for pid in range(1, N_PRODUCTS + 1):
            cat   = AMAZON_CATEGORIES[(pid - 1) % len(AMAZON_CATEGORIES)]
            title = make_product_name(cat, pid)
            price = round(random.uniform(4.99, 499.99), 2)
            avg_r = round(random.gauss(4.1, 0.6), 1)
            avg_r = max(1.0, min(5.0, avg_r))
            n_rat = int(np.random.exponential(300)) + 1
            brand = f"Brand-{pid % 500 + 1:04d}"
            prime = random.random() > 0.3
            w.writerow([pid, title, cat, price, avg_r, n_rat, brand, prime])
            if pid % 10_000 == 0:
                print(f"    … {pid:,} products done")
    print(f"  ✓ Products saved → {path}")


def generate_amazon_reviews(path: str):
    print(f"  Generating {N_REVIEWS:,} reviews (interactions) …")
    start_ts = datetime(2020, 1, 1).timestamp()
    end_ts   = datetime(2024, 12, 31).timestamp()

    # Power-law user & product distributions (realistic heavy-tail)
    user_weights    = np.random.zipf(1.3, N_USERS);    user_weights    = user_weights / user_weights.sum()
    product_weights = np.random.zipf(1.5, N_PRODUCTS); product_weights = product_weights / product_weights.sum()

    print("    Pre-sampling user and product distributions for high-speed generation …")
    # Batch sample 500K at a time to prevent np.random.choice bottleneck in Python loop
    BATCH_SIZE = 500_000

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["review_id", "user_id", "product_id", "rating", "event_type",
                    "timestamp", "session_id", "dwell_seconds"])
        
        rid = 1
        for batch_idx in range(0, N_REVIEWS, BATCH_SIZE):
            cur_batch_size = min(BATCH_SIZE, N_REVIEWS - batch_idx)
            batch_uids = np.random.choice(N_USERS, size=cur_batch_size, p=user_weights) + 1
            batch_pids = np.random.choice(N_PRODUCTS, size=cur_batch_size, p=product_weights) + 1
            
            for i in range(cur_batch_size):
                uid   = int(batch_uids[i])
                pid   = int(batch_pids[i])
                evt   = random.choice(EVENT_TYPES)
                rating = round(random.gauss(4.0, 1.0), 1) if evt in ("review", "purchase") else ""
                if rating != "":
                    rating = max(1.0, min(5.0, rating))
                ts    = int(random.uniform(start_ts, end_ts))
                sess  = f"S{uid:06d}-{random.randint(1, 50):04d}"
                dwell = int(np.random.exponential(45)) if evt == "view" else 0
                w.writerow([rid, uid, pid, rating, evt, ts, sess, dwell])
                rid += 1

            print(f"    … {rid - 1:,} / {N_REVIEWS:,} reviews done")
    print(f"  ✓ Reviews saved → {path}")


def generate_instacart_orders(orders_path: str, order_products_path: str,
                               products_path: str, aisles_path: str, depts_path: str):
    print(f"  Generating {N_ORDERS:,} Instacart orders …")

    # --- aisles ---
    os.makedirs(os.path.dirname(aisles_path), exist_ok=True)
    with open(aisles_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["aisle_id", "aisle"])
        for i, aisle in enumerate(INSTACART_AISLES[:N_AISLES], 1):
            w.writerow([i, aisle])

    # --- departments ---
    with open(depts_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["department_id", "department"])
        for i, dept in enumerate(INSTACART_DEPARTMENTS[:N_DEPARTMENTS], 1):
            w.writerow([i, dept])

    # --- products (grocery-style) ---
    grocery_items = [
        "Organic Whole Milk", "Greek Yogurt", "Large Eggs", "Sourdough Bread",
        "Chicken Breast", "Atlantic Salmon", "Cheddar Cheese", "Baby Spinach",
        "Cherry Tomatoes", "Avocado", "Banana", "Strawberries", "Blueberries",
        "Broccoli", "Brown Rice", "Quinoa", "Black Beans", "Olive Oil",
        "Pasta Sauce", "Orange Juice", "Sparkling Water", "Green Tea",
        "Almond Butter", "Granola Bar", "Dark Chocolate", "Frozen Waffles",
        "Frozen Burrito", "Canned Tuna", "Chicken Noodle Soup", "Peanut Butter",
        "Whole Wheat Bread", "Oat Milk", "Almond Milk", "Greek Salad Dressing",
        "Ranch Dressing", "Sriracha Sauce", "Soy Sauce", "Dijon Mustard",
        "Ketchup", "Mayo", "Cream Cheese", "Sour Cream", "Heavy Cream",
        "Butter", "Parmesan Cheese", "Mozzarella", "Cheddar Slices",
        "Turkey Deli Meat", "Ham", "Bacon", "Sausage Links"
    ]
    N_GROCERY = 5_000
    with open(products_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "product_name", "aisle_id", "department_id"])
        for pid in range(1, N_GROCERY + 1):
            base = grocery_items[(pid - 1) % len(grocery_items)]
            name = f"{base} {pid // len(grocery_items) + 1}" if pid > len(grocery_items) else base
            aisle_id = (pid - 1) % N_AISLES + 1
            dept_id  = (pid - 1) % N_DEPARTMENTS + 1
            w.writerow([pid, name, aisle_id, dept_id])

    # --- orders + order_products ---
    DOW  = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
    with open(orders_path, "w", newline="") as fo, \
         open(order_products_path, "w", newline="") as fp:
        wo = csv.writer(fo)
        wp = csv.writer(fp)
        wo.writerow(["order_id","user_id","eval_set","order_number","order_dow",
                     "order_hour_of_day","days_since_prior_order"])
        wp.writerow(["order_id","product_id","add_to_cart_order","reordered"])

        prod_counter = 0
        for oid in range(1, N_ORDERS + 1):
            uid      = random.randint(1, 200_000)
            eval_set = random.choices(["prior","train","test"], weights=[0.8,0.15,0.05])[0]
            ord_num  = random.randint(1, 100)
            dow      = random.randint(0, 6)
            hour     = random.randint(6, 23)
            days_gap = random.randint(1, 30) if random.random() > 0.05 else None
            wo.writerow([oid, uid, eval_set, ord_num, dow, hour,
                         days_gap if days_gap else ""])

            n_items = int(np.random.exponential(7)) + 1
            n_items = min(n_items, 30)
            items   = random.sample(range(1, N_GROCERY + 1), min(n_items, N_GROCERY))
            for pos, pid in enumerate(items, 1):
                reordered = 1 if random.random() > 0.4 else 0
                wp.writerow([oid, pid, pos, reordered])
                prod_counter += 1

            if oid % 300_000 == 0:
                print(f"    … {oid:,} orders done ({prod_counter:,} products)")

    print(f"  ✓ Instacart data saved")


def main():
    print("=" * 60)
    print(" Amazon + Instacart Synthetic Data Generator")
    print("=" * 60)

    t0 = time.time()

    # ── Amazon ──────────────────────────────────────────────────
    print("\n[1/2] Amazon Dataset")
    generate_amazon_products(os.path.join(BASE_DIR, "amazon_products.csv"))
    generate_amazon_reviews(os.path.join(BASE_DIR,  "amazon_reviews.csv"))

    # ── Instacart ────────────────────────────────────────────────
    print("\n[2/2] Instacart Dataset")
    generate_instacart_orders(
        orders_path        = os.path.join(BASE_DIR, "instacart_orders.csv"),
        order_products_path= os.path.join(BASE_DIR, "instacart_order_products.csv"),
        products_path      = os.path.join(BASE_DIR, "instacart_products.csv"),
        aisles_path        = os.path.join(BASE_DIR, "instacart_aisles.csv"),
        depts_path         = os.path.join(BASE_DIR, "instacart_departments.csv"),
    )

    elapsed = time.time() - t0
    print(f"\n✅ All datasets generated in {elapsed:.1f}s")
    print(f"   Saved to: {os.path.abspath(BASE_DIR)}")


if __name__ == "__main__":
    main()
