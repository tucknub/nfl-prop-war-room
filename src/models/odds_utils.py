from __future__ import annotations

import re
from typing import Any

import pandas as pd


def american_to_implied_probability(odds: Any) -> float | None:
    price = pd.to_numeric(odds, errors="coerce")
    if pd.isna(price) or float(price) == 0:
        return None
    price = float(price)
    if price < 0:
        return abs(price) / (abs(price) + 100)
    return 100 / (price + 100)


def normalize_market_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    aliases = {
        "rec": "receptions",
        "reception": "receptions",
        "receptions": "receptions",
        "receiving_yards": "receiving_yards",
        "receiving_yds": "receiving_yards",
        "rush_yards": "rushing_yards",
        "rushing_yards": "rushing_yards",
        "carries": "carries",
        "rush_attempts": "carries",
        "pass_attempts": "pass_attempts",
        "passing_attempts": "pass_attempts",
        "completions": "completions",
        "passing_yards": "passing_yards",
        "pass_yards": "passing_yards",
    }
    return aliases.get(text, text)


def validate_price(value: Any) -> bool:
    price = pd.to_numeric(value, errors="coerce")
    if pd.isna(price):
        return False
    price = float(price)
    return price != 0 and -10000 <= price <= 10000


def calculate_edge(model_probability: Any, implied_probability: Any) -> float | None:
    model = pd.to_numeric(model_probability, errors="coerce")
    implied = pd.to_numeric(implied_probability, errors="coerce")
    if pd.isna(model) or pd.isna(implied):
        return None
    return float(model) - float(implied)
