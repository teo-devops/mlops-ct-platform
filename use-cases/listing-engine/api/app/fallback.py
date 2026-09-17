"""Rules-based fraud check used when the model is slow, down or fused.

Degradation is a product decision: a slightly worse fraud check beats a
broken listing flow. The rules are deliberately simple and explainable.
"""

from __future__ import annotations

from app.config import Settings


def fraud_rules(
    title: str, price: float, category: str | None, s: Settings
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if price <= s.fallback_price_floor:
        reasons.append("price_at_floor")
    median = s.fallback_medians.get(category or "", None)
    if median and price < s.fallback_ratio_below_median * median:
        reasons.append("price_below_category_floor")
    lowered = title.lower()
    if any(k in lowered for k in s.fallback_keywords):
        reasons.append("suspicious_keyword")
    score = 0.9 if reasons else 0.05
    return score, reasons
