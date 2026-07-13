from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import nbformat
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation"
FOLD = OUT / "fold_1"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((OUT / "canonical_build_manifest.json").read_text(encoding="utf-8"))
    canonical = pd.read_csv(OUT / "canonical_player_week_role.csv.gz", low_memory=False)
    alerts = pd.read_csv(FOLD / "alerts_2021.csv.gz", low_memory=False)
    summary = pd.read_csv(FOLD / "summary_2021.csv")
    equal = pd.read_csv(FOLD / "equal_volume_verification_2021.csv")
    gates = pd.read_csv(FOLD / "fold_1_gate_diagnostic.csv")
    required = [
        "season", "week", "player_id", "player_name", "team", "position",
        "role_family", "metric_all", "metric_normal", "raw_opportunities_all",
        "raw_opportunities_normal", "team_opportunities_all", "team_opportunities_normal",
        "qualifying_game", "partial_game_flag", "data_quality_pass",
    ]
    key = ["season", "week", "player_id", "team", "role_family"]
    audit = canonical.loc[canonical["season"].between(2018, 2020)]
    recomputed = (
        alerts.loc[alerts["persistent"].notna()]
        .groupby(["role_family", "method"])["persistent"].mean()
    )
    reported = summary.set_index(["role_family", "method"])["precision"]
    notebook = nbformat.read(ROOT / "notebooks" / "role_change_validation.ipynb", as_version=4)
    notebook_errors = [
        output
        for cell in notebook.cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    checks = {
        "canonical_hash_matches_manifest": digest(OUT / "canonical_player_week_role.csv.gz") == manifest["canonical_sha256"],
        "protocol_exact_hash": digest(ROOT / "ROLE_CHANGE_VALIDATION_PROTOCOL.md") == "b9fcc357e98388bb15c2d7ae853620f8ccd6c2e60e491a6cfcb990bbfbfcadbe",
        "locked_decisions_exact_hash": digest(ROOT / "LOCKED_DECISIONS.md") == "57da1e3ebed077bd52709fb3331eb99e719c056e9e840d8c6913b512d7e4ba00",
        "canonical_rows_57928": len(canonical) == 57928,
        "audit_rows_20727": len(audit) == 20727,
        "zero_duplicate_keys": not audit.duplicated(key).any(),
        "zero_required_nulls": int(audit[required].isna().sum().sum()) == 0,
        "shares_in_range": canonical[["metric_all", "metric_normal"]].apply(lambda s: s.between(0, 1).all()).all(),
        "fold_only_2021": set(alerts["season"].unique()) == {2021},
        "equal_volume_all_family_weeks": bool(equal["equal_volume"].all()) and len(equal) == 72,
        "precision_recomputes": float((reported - recomputed).abs().max()) < 1e-12,
        "no_family_passes_all_point_gates": not bool(gates["all_point_gates_pass"].any()),
        "release_gates_unchanged": json.loads((OUT / "release_gate_integrity.json").read_text(encoding="utf-8"))["unchanged"],
        "notebook_executed_without_errors": not notebook_errors and all(
            cell.get("execution_count") is not None for cell in notebook.cells if cell.cell_type == "code"
        ),
    }
    checks = {name: bool(value) for name, value in checks.items()}
    result = {
        "validation_status": "Verified" if all(checks.values()) else "Failed verification",
        "analysis_readiness": "Needs revision",
        "public_detector_claim_supported": False,
        "checks": checks,
    }
    (OUT / "final_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
