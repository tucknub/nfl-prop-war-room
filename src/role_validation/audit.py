from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class AuditResult:
    passed: bool
    summary: pd.DataFrame
    issues: pd.DataFrame


def audit_player_week_table(
    df: pd.DataFrame,
    required_columns: list[str],
    key_columns: list[str],
    share_columns: list[str],
) -> AuditResult:
    issues: list[dict[str, Any]] = []

    missing = [column for column in required_columns if column not in df.columns]
    for column in missing:
        issues.append(
            {
                "severity": "critical",
                "check": "required_column",
                "field": column,
                "detail": "Required column is missing.",
            }
        )

    if not missing:
        duplicate_mask = df.duplicated(key_columns, keep=False)
        duplicate_count = int(duplicate_mask.sum())
        if duplicate_count:
            issues.append(
                {
                    "severity": "critical",
                    "check": "grain_uniqueness",
                    "field": ",".join(key_columns),
                    "detail": f"{duplicate_count} rows participate in duplicate keys.",
                }
            )

        for column in share_columns:
            values = pd.to_numeric(df[column], errors="coerce")
            invalid = values.notna() & ~values.between(0, 1)
            if invalid.any():
                issues.append(
                    {
                        "severity": "critical",
                        "check": "share_range",
                        "field": column,
                        "detail": f"{int(invalid.sum())} values are outside [0, 1].",
                    }
                )

        for column in ["season", "week", "player_id", "team", "role_family"]:
            null_count = int(df[column].isna().sum())
            if null_count:
                issues.append(
                    {
                        "severity": "critical",
                        "check": "not_null",
                        "field": column,
                        "detail": f"{null_count} null values.",
                    }
                )

        partial_rate = float(df["partial_game_flag"].fillna(False).mean())
        quality_pass_rate = float(df["data_quality_pass"].fillna(False).mean())
        qualifying_rate = float(df["qualifying_game"].fillna(False).mean())
    else:
        duplicate_count = None
        partial_rate = None
        quality_pass_rate = None
        qualifying_rate = None

    seasons = sorted(pd.to_numeric(df.get("season"), errors="coerce").dropna().unique().tolist()) if "season" in df else []
    summary = pd.DataFrame(
        [
            {"metric": "rows", "value": len(df)},
            {"metric": "columns", "value": len(df.columns)},
            {"metric": "seasons", "value": ",".join(map(str, seasons))},
            {"metric": "duplicate_key_rows", "value": duplicate_count},
            {"metric": "partial_game_rate", "value": partial_rate},
            {"metric": "quality_pass_rate", "value": quality_pass_rate},
            {"metric": "qualifying_game_rate", "value": qualifying_rate},
        ]
    )
    issues_df = pd.DataFrame(
        issues, columns=["severity", "check", "field", "detail"]
    )
    passed = issues_df.empty or not issues_df["severity"].eq("critical").any()
    return AuditResult(passed=passed, summary=summary, issues=issues_df)
