from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.operations.current_role_pipeline import (  # noqa: E402
    build_current_role_outputs,
    detect_completed_regular_weeks,
    load_partial_overrides,
    utc_now_iso,
    write_current_role_build,
)
from src.operations.nflverse_current import load_current_nflverse_sources  # noqa: E402


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def publish_staging(staging: Path, output_dir: Path) -> list[str]:
    published: list[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(staging.iterdir()):
        if not source.is_file():
            continue
        destination = output_dir / source.name
        temporary = destination.with_name(destination.name + ".tmp")
        shutil.copy2(source, temporary)
        temporary.replace(destination)
        published.append(destination.name)
    return published


def sanitized_source_manifest(source_manifest: pd.DataFrame) -> pd.DataFrame:
    result = source_manifest.copy()
    if "cache_path" in result:
        result["cache_path"] = result["cache_path"].fillna("").map(
            lambda value: Path(str(value)).name if str(value).strip() else ""
        )
    return result


def pipeline_status(
    *,
    season: int,
    status: str,
    generated_at_utc: str,
    message: str,
    through_week: int | None,
    completed_games: int,
    source_manifest: pd.DataFrame,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "season": season,
        "status": status,
        "generated_at_utc": generated_at_utc,
        "published_through_week": through_week,
        "completed_games": completed_games,
        "message": message,
        "source_status": sanitized_source_manifest(source_manifest).fillna("").to_dict("records"),
        "operational_policy": {
            "publication_grain": "consecutive fully completed regular-season weeks",
            "participation_data": "not used in-season because the current source is post-season only",
            "injury_data": "not inferred from an unavailable current source",
            "partial_game_handling": "manual reviewed overrides only",
            "snap_counts_required": True,
            "stale_cache_default": "blocked",
            "atomic_publication": True,
        },
    }
    if extra:
        payload.update(extra)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and publish fail-closed current-season PropWar role research outputs."
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--through-week", type=int)
    parser.add_argument(
        "--source-cache-dir",
        type=Path,
        default=ROOT / "data" / "cache" / "role_research",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "outputs" / "role_research"
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=ROOT / "outputs" / "run_reports" / "role_research",
    )
    parser.add_argument(
        "--partial-overrides",
        type=Path,
        default=ROOT / "data" / "operations" / "partial_game_overrides.csv",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--allow-stale-cache", action="store_true")
    parser.add_argument("--no-publish", action="store_true")
    args = parser.parse_args()

    generated_at = utc_now_iso()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = args.report_dir / f"role_research_attempt_{args.season}.json"
    completion_report_path = args.report_dir / f"completion_gate_{args.season}.csv"
    success_status_path = args.output_dir / f"role_research_status_{args.season}.json"

    sources, source_manifest = load_current_nflverse_sources(
        args.season,
        cache_dir=args.source_cache_dir,
        refresh=args.refresh,
        allow_stale_cache=args.allow_stale_cache,
    )
    source_manifest = sanitized_source_manifest(source_manifest)

    schedule_error = source_manifest.loc[source_manifest["source"].eq("schedules"), "error"]
    if schedule_error.empty or str(schedule_error.iloc[0]).strip():
        status = pipeline_status(
            season=args.season,
            status="BLOCKED",
            generated_at_utc=generated_at,
            message="Schedule source is unavailable; no current-season data was published.",
            through_week=None,
            completed_games=0,
            source_manifest=source_manifest,
        )
        write_json(attempt_path, status)
        print(json.dumps(status, indent=2))
        return 1

    completion = detect_completed_regular_weeks(
        sources["pbp"],
        sources["schedules"],
        args.season,
        requested_through_week=args.through_week,
    )
    completion.game_checks.to_csv(completion_report_path, index=False, lineterminator="\n")

    if completion.through_week is None:
        pbp_error = source_manifest.loc[source_manifest["source"].eq("pbp"), "error"]
        message = (
            "No fully completed regular-season week is available yet; "
            "existing published outputs were left untouched."
        )
        if not pbp_error.empty and str(pbp_error.iloc[0]).strip():
            message += " Current-season play-by-play is not available yet."
        status = pipeline_status(
            season=args.season,
            status="WAITING_FOR_COMPLETED_WEEK",
            generated_at_utc=generated_at,
            message=message,
            through_week=None,
            completed_games=0,
            source_manifest=source_manifest,
            extra={
                "completed_weeks": [],
                "blocked_weeks": list(completion.blocked_weeks),
                "completion_gate_file": completion_report_path.name,
            },
        )
        write_json(attempt_path, status)
        print(json.dumps(status, indent=2))
        return 0

    critical_sources = ("pbp", "player_stats", "rosters_weekly", "snap_counts")
    critical_errors = source_manifest.loc[
        source_manifest["source"].isin(critical_sources)
        & source_manifest["error"].fillna("").astype(str).str.strip().ne("")
    ]
    if not critical_errors.empty:
        status = pipeline_status(
            season=args.season,
            status="BLOCKED",
            generated_at_utc=generated_at,
            message=(
                "One or more required current-season sources failed; "
                "the prior published partition remains active."
            ),
            through_week=completion.through_week,
            completed_games=len(completion.completed_game_ids),
            source_manifest=source_manifest,
            extra={"critical_source_errors": critical_errors.to_dict("records")},
        )
        write_json(attempt_path, status)
        print(json.dumps(status, indent=2))
        return 1

    overrides = load_partial_overrides(
        args.partial_overrides if args.partial_overrides.exists() else None,
        args.season,
        completion.through_week,
    )
    try:
        nflreadpy_versions = source_manifest["nflreadpy_version"].dropna().astype(str).unique().tolist()
        source_version = (
            f"nflreadpy {nflreadpy_versions[0]} · current-season play-by-play, weekly rosters, and snap counts"
            if nflreadpy_versions
            else "current-season play-by-play, weekly rosters, and snap counts"
        )
        build = build_current_role_outputs(
            season=args.season,
            through_week=completion.through_week,
            completed_game_ids=completion.completed_game_ids,
            pbp=sources["pbp"],
            player_stats=sources["player_stats"],
            rosters_weekly=sources["rosters_weekly"],
            snap_counts=sources["snap_counts"],
            schedules=sources["schedules"],
            partial_overrides=overrides,
            source_version=source_version,
            generated_at_utc=generated_at,
        )
        run_id = f"{args.season}-{completion.through_week}-{uuid.uuid4().hex[:10]}"
        staging = args.output_dir / ".staging" / run_id
        staging.mkdir(parents=True, exist_ok=False)
        written = write_current_role_build(build, staging)
        source_manifest_path = staging / f"source_input_manifest_{args.season}_live.csv"
        source_manifest.to_csv(source_manifest_path, index=False, lineterminator="\n")
        completion_staging_path = staging / f"completion_gate_{args.season}.csv"
        completion.game_checks.to_csv(completion_staging_path, index=False, lineterminator="\n")
        published_files = [] if args.no_publish else publish_staging(staging, args.output_dir)
        status = pipeline_status(
            season=args.season,
            status="VALIDATED_NOT_PUBLISHED" if args.no_publish else "PUBLISHED",
            generated_at_utc=generated_at,
            message=(
                "Current-season role research validated in staging only."
                if args.no_publish
                else f"Published through Week {completion.through_week} after all completed-week gates passed."
            ),
            through_week=completion.through_week,
            completed_games=len(completion.completed_game_ids),
            source_manifest=source_manifest,
            extra={
                "completed_weeks": list(completion.completed_weeks),
                "blocked_weeks": list(completion.blocked_weeks),
                "staging_run_id": run_id,
                "staging_files": sorted(Path(value).name for value in written.values()),
                "published_files": published_files,
                "partial_override_rows": int(len(overrides)),
            },
        )
        write_json(attempt_path, status)
        if not args.no_publish:
            write_json(success_status_path, status)
        print(json.dumps(status, indent=2))
        return 0
    except Exception as exc:
        status = pipeline_status(
            season=args.season,
            status="BLOCKED",
            generated_at_utc=generated_at,
            message=(
                "Validation or publication failed; "
                "the prior published partition remains active."
            ),
            through_week=completion.through_week,
            completed_games=len(completion.completed_game_ids),
            source_manifest=source_manifest,
            extra={"error": f"{type(exc).__name__}: {exc}"},
        )
        write_json(attempt_path, status)
        print(json.dumps(status, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
