from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
SOURCE = OUT / "original_false_positive_case_review_2021.csv"
TARGET = OUT / "original_false_positive_manual_adjudication_2021.csv"
MANIFEST_TARGET = OUT / "manual_review_manifest.json"
KEY = ["season", "week", "player_id", "team", "role_family"]


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--review",
        default="config/fold1_false_positive_manual_review.yaml",
    )
    args = parser.parse_args()
    review_path = ROOT / args.review
    review = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    source_hash = digest(SOURCE)
    if source_hash != review["source_sha256"]:
        raise AssertionError(
            f"Manual review source changed: expected {review['source_sha256']}, got {source_hash}"
        )
    frame = pd.read_csv(SOURCE, low_memory=False)
    if len(frame) != int(review["reviewed_rows"]):
        raise AssertionError("Manual-review row count differs from the reviewed manifest")
    if not bool(review["row_by_row_review_completed"]):
        raise AssertionError("Review manifest does not attest a completed row-by-row review")
    if frame.duplicated(KEY).any():
        raise AssertionError("False-positive review source is not unique at family-alert grain")

    frame["manual_primary_reason_code"] = frame["primary_reason_code"]
    frame["manual_secondary_reason_codes"] = frame["secondary_reason_codes"].fillna("")
    frame["manual_override_applied"] = False
    frame["manual_override_basis"] = ""
    frame["manual_note"] = frame["reviewer_note"]
    override_keys: set[tuple[object, ...]] = set()
    for adjudication in review.get("category_adjudications", []):
        action = adjudication["action"]
        if action == "reclassify_decrease_current_opportunity":
            mask = frame["primary_reason_code"].eq("LOW_PLAYER_OPPORTUNITY_NOISE") & frame[
                "direction"
            ].eq("decrease")
            priority = adjudication["fallback_priority"]
            for index in frame.index[mask]:
                secondary = str(frame.at[index, "secondary_reason_codes"])
                replacement = next(
                    (code for code in priority if code in secondary),
                    "ROLE_REVERSION_NO_OBSERVED_DATA_ISSUE",
                )
                frame.at[index, "manual_primary_reason_code"] = replacement
                retained = "" if secondary == "nan" else secondary
                context = "CURRENT_LOW_OPPORTUNITY_EXPECTED_FOR_DETECTED_DECREASE"
                frame.at[index, "manual_secondary_reason_codes"] = " | ".join(
                    value for value in [retained, context] if value
                )
                frame.at[index, "manual_note"] = (
                    "Current low opportunity is the detected decrease, not independent noise; "
                    f"manual review reassigned the case to {replacement}."
                )
                frame.at[index, "manual_override_applied"] = True
                frame.at[index, "manual_override_basis"] = adjudication["id"]
                override_keys.add(tuple(frame.loc[index, KEY]))
            observed_count = int(mask.sum())
        elif action == "rename_suspected_teammate_context":
            mask = frame["primary_reason_code"].eq(
                "SUSPECTED_TEAMMATE_EXIT_BENEFICIARY"
            )
            frame.loc[mask, "manual_primary_reason_code"] = (
                "SUSPECTED_TEAMMATE_EXIT_CONTEXT"
            )
            frame.loc[mask, "manual_note"] = (
                "A suspected same-position teammate exit was observed; it is retained as context, "
                "not asserted as a causal beneficiary mechanism."
            )
            frame.loc[mask, "manual_override_applied"] = True
            frame.loc[mask, "manual_override_basis"] = adjudication["id"]
            override_keys.update(
                tuple(row) for row in frame.loc[mask, KEY].itertuples(index=False, name=None)
            )
            observed_count = int(mask.sum())
        else:
            raise ValueError(f"Unknown category adjudication action: {action}")
        if observed_count != int(adjudication["reviewed_case_count"]):
            raise AssertionError(
                f"{adjudication['id']} expected {adjudication['reviewed_case_count']} rows, "
                f"found {observed_count}"
            )
    for override in review.get("overrides", []):
        key = tuple(override[column] for column in KEY)
        mask = pd.Series(True, index=frame.index)
        for column, value in zip(KEY, key):
            mask &= frame[column].eq(value)
        if int(mask.sum()) != 1:
            raise AssertionError(f"Manual override key matched {int(mask.sum())} rows: {key}")
        frame.loc[mask, "manual_primary_reason_code"] = override["manual_primary_reason_code"]
        frame.loc[mask, "manual_secondary_reason_codes"] = override.get(
            "manual_secondary_reason_codes", ""
        )
        frame.loc[mask, "manual_override_applied"] = True
        frame.loc[mask, "manual_override_basis"] = "explicit_row_override"
        frame.loc[mask, "manual_note"] = override["manual_note"]
        override_keys.add(key)

    accepted = set(review["accepted_reason_codes"])
    observed = set(frame["manual_primary_reason_code"].dropna().astype(str))
    if not observed.issubset(accepted):
        raise AssertionError(f"Unapproved manual reason codes: {sorted(observed - accepted)}")
    frame["manual_review_status"] = "MANUALLY_ADJUDICATED"
    frame["manual_reviewer"] = review["reviewer"]
    frame["manual_reviewed_at_utc"] = review["reviewed_at_utc"]
    frame["manual_review_basis"] = review["review_basis"]
    frame.to_csv(TARGET, index=False)

    result = {
        "status": "COMPLETE",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": source_hash,
        "review_config": str(review_path.relative_to(ROOT)).replace("\\", "/"),
        "review_config_sha256": digest(review_path),
        "reviewed_rows": len(frame),
        "overrides": len(override_keys),
        "reviewer": review["reviewer"],
        "reviewed_at_utc": review["reviewed_at_utc"],
        "row_by_row_review_completed": True,
        "manual_reason_counts": frame["manual_primary_reason_code"].value_counts().to_dict(),
    }
    MANIFEST_TARGET.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
