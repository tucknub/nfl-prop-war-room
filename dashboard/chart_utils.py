from __future__ import annotations

import json
from typing import Any

import pandas as pd


def dataframe_inline_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Serialize a small pandas frame to JSON-native records for chart libraries.

    Passing a native DataFrame into Altair triggers its dataframe-compatibility
    bridge (Narwhals), which can inspect optional dataframe backends such as
    Polars. Small UI datasets are safer as explicit inline Vega-Lite records.
    """
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso"))


__all__ = ["dataframe_inline_records"]
