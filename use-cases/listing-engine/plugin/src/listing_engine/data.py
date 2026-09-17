"""Synthetic listings, seeded and reproducible.

A real deployment plugs an ETL here (the `ingest` step contract does not
care). The generator has a `drift` profile that changes the world the way a
marketplace does after a season: prices collapse, a category takes over and
new vocabulary appears — enough to move the PSI past the retrain threshold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

CATEGORIES = ("electronics", "fashion", "home", "sports", "books", "kids")

# vocabulary per category and a log-normal price distribution (median, sigma)
VOCAB: dict[str, list[str]] = {
    "electronics": [
        "iphone",
        "samsung",
        "laptop",
        "headphones",
        "tablet",
        "camera",
        "ps5",
        "monitor",
        "gpu",
        "smartwatch",
    ],
    "fashion": [
        "jacket",
        "sneakers",
        "dress",
        "jeans",
        "handbag",
        "coat",
        "boots",
        "sunglasses",
        "watch",
        "scarf",
    ],
    "home": [
        "sofa",
        "table",
        "lamp",
        "chair",
        "shelf",
        "mattress",
        "rug",
        "desk",
        "wardrobe",
        "mirror",
    ],
    "sports": [
        "bike",
        "skis",
        "tennis",
        "dumbbells",
        "surfboard",
        "helmet",
        "treadmill",
        "kayak",
        "golf",
        "yoga",
    ],
    "books": [
        "novel",
        "textbook",
        "comic",
        "manga",
        "cookbook",
        "atlas",
        "encyclopedia",
        "biography",
        "poetry",
        "guide",
    ],
    "kids": [
        "stroller",
        "lego",
        "crib",
        "toy",
        "puzzle",
        "scooter",
        "doll",
        "playmat",
        "carseat",
        "tricycle",
    ],
}
QUALIFIERS = [
    "new",
    "like new",
    "used",
    "good condition",
    "vintage",
    "original",
    "sealed",
    "barely used",
    "2023",
    "pro",
]
PRICE: dict[str, tuple[float, float]] = {
    "electronics": (350.0, 0.7),
    "fashion": (40.0, 0.7),
    "home": (90.0, 0.8),
    "sports": (120.0, 0.8),
    "books": (12.0, 0.6),
    "kids": (45.0, 0.7),
}
FRAUD_WORDS = [
    "urgent",
    "whatsapp",
    "western union",
    "paypal friends",
    "shipping only",
    "deposit first",
]

DRIFT_VOCAB = {
    "electronics": ["foldable", "e-bike", "drone", "vr headset", "airpods"],
    "fashion": ["y2k", "thrift", "cargo"],
}


def generate(seed: int, rows: int, profile: str | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    drift = profile == "drift"
    weights = np.array([0.30, 0.22, 0.15, 0.12, 0.11, 0.10])
    if drift:
        # after the season: electronics floods the marketplace
        weights = np.array([0.55, 0.15, 0.08, 0.07, 0.08, 0.07])
    category = rng.choice(CATEGORIES, size=rows, p=weights / weights.sum())

    titles, prices, fraud = [], [], []
    for cat in category:
        vocab = VOCAB[cat] + (DRIFT_VOCAB.get(cat, []) * 3 if drift else [])
        words = [rng.choice(vocab), rng.choice(QUALIFIERS)]
        if rng.random() < 0.5:
            words.append(rng.choice(vocab))
        median, sigma = PRICE[cat]
        price = float(np.exp(rng.normal(np.log(median), sigma)))
        if drift:
            price *= 0.25  # prices collapse (post-season)
        is_fraud = False
        r = rng.random()
        if r < 0.06:  # too cheap for what it claims to be
            price = median * float(rng.uniform(0.02, 0.12))
            is_fraud = True
        elif r < 0.10:  # social-engineering wording
            words.append(rng.choice(FRAUD_WORDS))
            is_fraud = True
        # label noise: some frauds go unnoticed, some legit listings get flagged
        if rng.random() < 0.02:
            is_fraud = not is_fraud
        titles.append(" ".join(words))
        prices.append(round(max(price, 0.5), 2))
        fraud.append(is_fraud)

    return pd.DataFrame(
        {
            "title": titles,
            "price": prices,
            "category": category,
            "is_fraud": fraud,
        }
    )
