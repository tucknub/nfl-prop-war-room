from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from src.common import output_path


@dataclass(frozen=True)
class MarketMetadata:
    market_key: str
    display_name: str
    category: str
    status: str
    active: bool
    projection_unit: str
    requires_odds: bool
    requires_roster_gate: bool
    requires_role_gate: bool
    requires_injury_gate: bool
    notes: str


MARKETS = [
    MarketMetadata(
        "receptions",
        "Receptions",
        "Receiving",
        "built",
        True,
        "receptions",
        True,
        True,
        True,
        True,
        "Receptions V1 is the active historical-test market with projections, line ladder, and blocked edge engine.",
    ),
    MarketMetadata(
        "receiving_yards",
        "Receiving Yards",
        "Receiving",
        "built_historical_test",
        True,
        "receiving_yards",
        True,
        True,
        True,
        True,
        "Receiving Yards V1 historical-test market using projected receptions and yards-per-reception efficiency.",
    ),
    MarketMetadata(
        "rushing_yards",
        "Rushing Yards",
        "Rushing",
        "built_historical_test",
        True,
        "rushing_yards",
        True,
        True,
        True,
        True,
        "Rushing Yards V1 historical-test market using projected carries and yards-per-carry efficiency.",
    ),
    MarketMetadata(
        "passing_yards",
        "Passing Yards",
        "Passing",
        "planned - not built yet",
        False,
        "yards",
        True,
        True,
        True,
        True,
        "Planned QB/team pass-volume and efficiency market.",
    ),
    MarketMetadata(
        "completions",
        "Completions",
        "Passing",
        "planned - not built yet",
        False,
        "completions",
        True,
        True,
        True,
        True,
        "Planned passing-volume market tied to QB attempts and completion rate.",
    ),
    MarketMetadata(
        "pass_attempts",
        "Pass Attempts",
        "Passing",
        "planned - not built yet",
        False,
        "attempts",
        True,
        True,
        True,
        True,
        "Planned team/QB pass-volume market.",
    ),
    MarketMetadata(
        "carries",
        "Carries",
        "Rushing",
        "planned - not built yet",
        False,
        "carries",
        True,
        True,
        True,
        True,
        "Planned rushing opportunity market.",
    ),
    MarketMetadata(
        "targets",
        "Targets",
        "Receiving",
        "planned - not built yet",
        False,
        "targets",
        True,
        True,
        True,
        True,
        "Planned receiving opportunity market adjacent to Receptions V1.",
    ),
    MarketMetadata(
        "anytime_td",
        "Anytime TD",
        "Touchdowns",
        "planned - not built yet",
        False,
        "touchdown probability",
        True,
        True,
        True,
        True,
        "Planned later because TD props need different event probability modeling.",
    ),
    MarketMetadata(
        "longest_reception",
        "Longest Reception",
        "Long Plays",
        "planned - not built yet",
        False,
        "yards",
        True,
        True,
        True,
        True,
        "Planned long-play distribution market; not part of Receptions V1.",
    ),
    MarketMetadata(
        "longest_rush",
        "Longest Rush",
        "Long Plays",
        "planned - not built yet",
        False,
        "yards",
        True,
        True,
        True,
        True,
        "Planned long-play rushing distribution market; not part of Receptions V1.",
    ),
]


def market_registry_df() -> pd.DataFrame:
    return pd.DataFrame([asdict(market) for market in MARKETS])


def export_market_status() -> pd.DataFrame:
    df = market_registry_df()
    export_cols = [
        "market_key",
        "display_name",
        "category",
        "status",
        "active",
        "projection_unit",
        "requires_odds",
        "notes",
    ]
    out = df[export_cols].copy()
    output_path("markets/market_status.csv").parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path("markets/market_status.csv"), index=False)
    return out


def main() -> None:
    out = export_market_status()
    print(f"market_status: {len(out):,} rows")
    active = out[out["active"] == True]["market_key"].tolist()  # noqa: E712
    print(f"active_markets: {', '.join(active) if active else 'None'}")


if __name__ == "__main__":
    main()
