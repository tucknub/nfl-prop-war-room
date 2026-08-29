from __future__ import annotations

import altair as alt
import pandas as pd

from dashboard.chart_utils import dataframe_inline_records


def test_dataframe_inline_records_are_json_native_and_null_safe():
    frame = pd.DataFrame(
        {
            "Week": [1, 2],
            "Series": ["Normal game", "Normal game"],
            "value": [0.25, 0.50],
            "Raw": [5, 10],
            "Denominator": [20, None],
        }
    )

    records = dataframe_inline_records(frame)

    assert records == [
        {
            "Week": 1,
            "Series": "Normal game",
            "value": 0.25,
            "Raw": 5,
            "Denominator": 20.0,
        },
        {
            "Week": 2,
            "Series": "Normal game",
            "value": 0.5,
            "Raw": 10,
            "Denominator": None,
        },
    ]


def test_altair_player_chart_serializes_from_inline_data_without_native_dataframe_bridge():
    frame = pd.DataFrame(
        {
            "Week": [1, 2],
            "Series": ["Normal game", "Normal game"],
            "value": [0.25, 0.50],
            "Raw": [5, 10],
            "Denominator": [20, 20],
        }
    )
    source = alt.Data(values=dataframe_inline_records(frame))
    chart = (
        alt.Chart(source)
        .mark_line(point=True)
        .encode(
            x=alt.X("Week:Q"),
            y=alt.Y("value:Q"),
            color=alt.Color("Series:N"),
            tooltip=[
                alt.Tooltip("Week:Q"),
                alt.Tooltip("value:Q"),
                alt.Tooltip("Raw:Q"),
                alt.Tooltip("Denominator:Q"),
            ],
        )
    )

    spec = chart.to_dict()

    assert spec["data"]["values"][0]["Week"] == 1
    assert spec["data"]["values"][1]["value"] == 0.5


def test_players_page_uses_inline_records_for_weekly_altair_chart():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (
        root / "dashboard" / "pages" / "02_Players.py"
    ).read_text(encoding="utf-8")

    assert "dataframe_inline_records(chart_data)" in source
    assert "alt.Data(values=" in source
    assert "alt.Chart(chart_data)" not in source
