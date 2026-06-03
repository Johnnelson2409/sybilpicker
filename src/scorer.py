"""
scorer.py - Aggregate per-signal scores into a 0-100 sybil score.

Weighted average of the per-signal scores (each in [0, 1]). The
weights are calibrated so a wallet that triggers every "sybil"
signal scores 100, and a wallet that triggers none scores 0.
"""
from __future__ import annotations
from typing import List

from signals import SignalResult


WEIGHTS = {
    "funding_source":      25,
    "wallet_age":          20,
    "funding_dispersion":  15,
    "dormancy_ratio":      15,
    "activity_regularity": 15,
    "asset_variety":       10,
}


def score(signals: List[SignalResult]) -> int:
    if not signals:
        return 0
    earned = 0.0
    total = 0
    for s in signals:
        w = WEIGHTS.get(s.name, 0)
        if w == 0:
            continue
        earned += w * max(0.0, min(1.0, s.score))
        total += w
    if total == 0:
        return 0
    pct = earned / total
    return max(0, min(100, int(round(pct * 100))))


def label(score_val: int) -> str:
    if score_val < 20:
        return "HUMAN"
    if score_val < 40:
        return "LOW_RISK"
    if score_val < 60:
        return "MEDIUM_RISK"
    if score_val < 80:
        return "HIGH_RISK"
    return "LIKELY_SYBIL"


def action(label_val: str) -> str:
    return {
        "HUMAN":         "Allow. Looks like a normal user.",
        "LOW_RISK":      "Allow with light review.",
        "MEDIUM_RISK":   "Manual review before allowing.",
        "HIGH_RISK":     "Reject unless strong counter-evidence.",
        "LIKELY_SYBIL":  "Reject. Almost certainly a farmed account.",
    }.get(label_val, "")


def dominant_signal(signals: List[SignalResult]) -> SignalResult:
    """The signal that contributed most to the sybil score."""
    if not signals:
        return None  # type: ignore[return-value]
    return max(signals, key=lambda s: WEIGHTS.get(s.name, 0) * s.score)
