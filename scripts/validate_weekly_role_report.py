from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "weekly_role_report"
sys.path.insert(0, str(ROOT / "dashboard"))

from weekly_report import DISPLAY_CATEGORIES, build_weekly_role_report  # noqa: E402


WEEKS = [2, 5, 8, 11, 14, 18]
REQUIRED = [
    "WEEKLY_ROLE_REPORT_DESIGN.md",
    "SCREENING_RULES.md",
    "historical_replay_summary.csv",
    "historical_replay_cards.csv",
    "historical_replay_findings.md",
    "duplicate_category_assignments.csv",
    "mobile_qa.md",
    "desktop_qa.md",
    "final_validation.json",
    "COMMANDS_RUN.md",
]


def main() -> int:
    failures: list[str] = []
    missing = [name for name in REQUIRED if not (OUT / name).exists()]
    failures.extend(f"missing artifact: {name}" for name in missing)
    if missing:
        print("\n".join(failures))
        return 1

    summary = pd.read_csv(OUT / "historical_replay_summary.csv")
    cards_archive = pd.read_csv(OUT / "historical_replay_cards.csv", dtype={"player_id": str})
    if summary["week"].tolist() != WEEKS:
        failures.append("fixed replay weeks do not match")
    if not summary["displayed_total"].between(8, 15).all():
        failures.append("default volume outside 8–15")
    if cards_archive.duplicated(["season", "week", "player_id"]).any():
        failures.append("duplicate default player-week cards")

    regenerated: list[pd.DataFrame] = []
    for week in WEEKS:
        cards, _ = build_weekly_role_report(2025, week)
        regenerated.append(cards)
        if not cards["week"].eq(week).all():
            failures.append(f"Week {week}: selected-week mismatch")
        if not np.allclose(cards["current_share"], cards["current_raw"] / cards["current_denominator"]):
            failures.append(f"Week {week}: current share reconciliation")
        if cards["player_id"].duplicated().any():
            failures.append(f"Week {week}: duplicate default player")
        if cards.groupby("category").size().gt(3).any():
            failures.append(f"Week {week}: category cap exceeded")
        for _, row in cards.iterrows():
            link_expectations = [
                (row["player_href"], {"season": "2025", "week": str(week), "player": row["player_id"]}),
                (row["team_href"], {"season": "2025", "week": str(week), "team": row["team"]}),
                (row["game_href"], {"season": "2025", "week": str(week), "game": row["game_id"]}),
            ]
            for href, expected in link_expectations:
                query = {key: values[0] for key, values in parse_qs(urlparse(href).query).items()}
                if not all(str(query.get(key)) == str(value) for key, value in expected.items()):
                    failures.append(f"Week {week}: invalid evidence link {href}")

    regenerated_frame = pd.concat(regenerated, ignore_index=True)
    archive_keys = cards_archive[["season", "week", "player_id", "category"]].astype(str)
    generated_keys = regenerated_frame[["season", "week", "player_id", "category"]].astype(str)
    if set(archive_keys.itertuples(index=False, name=None)) != set(generated_keys.itertuples(index=False, name=None)):
        failures.append("replay archive differs from regenerated report")
    if set(cards_archive["category"].unique()) != set(DISPLAY_CATEGORIES):
        failures.append("one or more required categories absent from archive")

    manifest_path = OUT / "final_validation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["independent_output_validation"] = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "required_artifact_count": len(REQUIRED),
        "regenerated_default_cards": int(len(regenerated_frame)),
        "archive_default_cards": int(len(cards_archive)),
    }
    manifest["status"] = "PASS" if not failures else "FAIL"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if failures:
        print("WEEKLY ROLE REPORT VALIDATION FAILED")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print(f"WEEKLY ROLE REPORT VALIDATION PASSED: {len(regenerated_frame)} replay cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
