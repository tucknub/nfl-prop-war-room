from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from role_validation.audit import audit_player_week_table
from role_validation.config import load_config, verify_frozen_config
from role_validation.evaluation import release_decision
from role_validation.workflow import run_fold


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PropWar role-change validation.")
    parser.add_argument("--input", required=True, help="Canonical player-week-role CSV, CSV.GZ, or Parquet.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fold", default="fold_1")
    parser.add_argument("--mode", choices=["development", "final_holdout"], default="development")
    return parser.parse_args()


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(args.config)
    if args.mode == "final_holdout":
        verify_frozen_config(config)

    data = load_table(input_path)
    audit = audit_player_week_table(
        data,
        required_columns=config["data"]["required_columns"],
        key_columns=config["data"]["key_columns"],
        share_columns=config["data"]["share_columns"],
    )
    audit.summary.to_csv(output_dir / "data_audit_summary.csv", index=False)
    audit.issues.to_csv(output_dir / "data_audit_issues.csv", index=False)
    if not audit.passed:
        raise SystemExit("Critical data-audit failures. See data_audit_issues.csv.")

    fold_config = next((fold for fold in config["folds"] if fold["name"] == args.fold), None)
    if args.mode == "final_holdout":
        fold_config = next(fold for fold in config["folds"] if fold["name"] == "final_holdout")
    if fold_config is None:
        raise SystemExit(f"Unknown fold: {args.fold}")
    start_season = int(config["project"]["start_season"])
    development_seasons = list(range(start_season, int(fold_config["develop_through"]) + 1))
    test_season = int(fold_config["test_season"])
    result = run_fold(
        data,
        config,
        development_seasons=development_seasons,
        test_season=test_season,
        minimum_development_evaluable_alerts=int(
            config.get("development_selection", {}).get("min_evaluable_alerts", 25)
        ),
    )
    result.tuning_results.to_csv(output_dir / f"{args.fold}_development_grid.csv", index=False)
    result.selected_parameters.to_csv(output_dir / f"{args.fold}_selected_parameters.csv", index=False)
    result.alerts.to_csv(
        output_dir / f"alerts_{test_season}.csv.gz",
        index=False,
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )
    result.summary.to_csv(output_dir / f"summary_{test_season}.csv", index=False)
    result.comparisons.to_csv(output_dir / f"comparisons_{test_season}.csv", index=False)
    result.weekly_counts.to_csv(output_dir / f"weekly_alert_counts_{test_season}.csv", index=False)
    result.equal_volume.to_csv(output_dir / f"equal_volume_verification_{test_season}.csv", index=False)
    if len(result.equal_volume) and not result.equal_volume["equal_volume"].all():
        raise SystemExit("Equal-volume verification failed.")

    if args.mode == "final_holdout":
        decisions = release_decision(
            result.summary,
            gates=config["release_gates"]["full_release"],
        )
        decisions.to_csv(output_dir / "release_decisions_2025.csv", index=False)

    manifest = {
        "mode": args.mode,
        "fold": args.fold,
        "input": str(input_path),
        "development_seasons": development_seasons,
        "test_season": test_season,
        "rows": len(data),
        "alert_rows_all_methods": len(result.alerts),
        "full_propwar_alerts": int(result.alerts["method"].eq("full_propwar").sum()) if len(result.alerts) else 0,
        "equal_volume_family_weeks": len(result.equal_volume),
        "equal_volume_verified": bool(result.equal_volume["equal_volume"].all()) if len(result.equal_volume) else True,
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
