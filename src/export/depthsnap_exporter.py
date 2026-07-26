from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.load.build_identity_crosswalk import TEAM_VARIANTS, canonical_team
from src.operations.published_validation import validate_published_role_outputs


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = REPO_ROOT / "dashboard"
if str(DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_ROOT))

from launch_contract import REPORT_DEFINITIONS, REPORT_FAMILIES  # noqa: E402
from research_data import (  # noqa: E402
    league_window_summary,
    load_role_data,
    primary_rows,
)
from weekly_report import (  # noqa: E402
    CATEGORY_GAINED,
    CATEGORY_LOST,
    CATEGORY_OVERSTATED,
    CATEGORY_WEAK_PRODUCTION,
    build_weekly_role_report,
    default_home_week,
)


SCHEMA_VERSIONS = {
    "home": "depthsnap.home.v1",
    "reports_index": "depthsnap.reports.index.v1",
    "report_backfield": "depthsnap.report.backfield.v1",
    "report_targets": "depthsnap.report.targets.v1",
    "report_movement": "depthsnap.report.movement.v1",
    "teams_index": "depthsnap.teams.index.v1",
    "team": "depthsnap.team.v1",
    "players_index": "depthsnap.players.index.v1",
    "player": "depthsnap.player.v1",
    "search": "depthsnap.search.v1",
    "status": "depthsnap.status.v1",
}
ROLE_LABELS = {
    "rb_carry_share": "RB carry share",
    "rb_opportunity_share": "RB opportunity share",
    "wr_target_share": "WR target share",
    "te_target_share": "TE target share",
}
OPPORTUNITY_LABELS = {
    "rb_carry_share": "carries",
    "rb_opportunity_share": "opportunities",
    "wr_target_share": "targets",
    "te_target_share": "targets",
}
REPORT_PUBLIC_FAMILIES = {
    "Backfield Control": "backfield_control",
    "Target Hierarchy": "target_hierarchy",
    "Role Movement": "role_movement",
}
REPORT_BUNDLE_FAMILIES = {
    "Backfield Control": "report_backfield",
    "Target Hierarchy": "report_targets",
    "Role Movement": "report_movement",
}
REPORT_PATHS = {
    "backfield_control": "/reports/backfield",
    "target_hierarchy": "/reports/targets",
    "role_movement": "/reports/movement",
}
REPORT_TITLES = {value: key for key, value in REPORT_PUBLIC_FAMILIES.items()}
FINDING_KINDS = {
    CATEGORY_GAINED: "opportunity_gained",
    CATEGORY_LOST: "opportunity_lost",
    CATEGORY_OVERSTATED: "box_score_overstated_role",
    CATEGORY_WEAK_PRODUCTION: "strong_opportunity_weak_production",
}
VIEW_WINDOWS: tuple[tuple[str, str, int | str], ...] = (
    ("last4", "Last 4", 4),
    ("last8", "Last 8", 8),
    ("last2", "Last 2", 2),
    ("season", "Season", "Season"),
)
MINIMUM_REPORT_SAMPLE = 8

TEAM_ALIGNMENT = {
    "ARI": ("NFC", "West"),
    "ATL": ("NFC", "South"),
    "BAL": ("AFC", "North"),
    "BUF": ("AFC", "East"),
    "CAR": ("NFC", "South"),
    "CHI": ("NFC", "North"),
    "CIN": ("AFC", "North"),
    "CLE": ("AFC", "North"),
    "DAL": ("NFC", "East"),
    "DEN": ("AFC", "West"),
    "DET": ("NFC", "North"),
    "GB": ("NFC", "North"),
    "HOU": ("AFC", "South"),
    "IND": ("AFC", "South"),
    "JAX": ("AFC", "South"),
    "KC": ("AFC", "West"),
    "LAC": ("AFC", "West"),
    "LAR": ("NFC", "West"),
    "LV": ("AFC", "West"),
    "MIA": ("AFC", "East"),
    "MIN": ("NFC", "North"),
    "NE": ("AFC", "East"),
    "NO": ("NFC", "South"),
    "NYG": ("NFC", "East"),
    "NYJ": ("AFC", "East"),
    "PHI": ("NFC", "East"),
    "PIT": ("AFC", "North"),
    "SEA": ("NFC", "West"),
    "SF": ("NFC", "West"),
    "TB": ("NFC", "South"),
    "TEN": ("AFC", "South"),
    "WAS": ("NFC", "East"),
}

PUBLIC_DATA_ROOT = REPO_ROOT / "apps" / "web" / "public" / "data" / "depthsnap"
ACTIVE_EXPORT_DIRECTORY = PUBLIC_DATA_ROOT / "export"
HISTORICAL_EXPORT_DIRECTORY = PUBLIC_DATA_ROOT / "export-historical-2025"
ACTIVE_STATUS_PATH = REPO_ROOT / "outputs" / "role_research" / "role_research_status_2026.json"
CURRENT_ROLE_OUTPUT_DIRECTORY = REPO_ROOT / "outputs" / "role_research"
HISTORICAL_SOURCE_PATHS = (
    REPO_ROOT / "outputs" / "role_research" / "canonical_role_2025_descriptive.csv.gz",
    REPO_ROOT / "outputs" / "role_research" / "canonical_audit_2025.json",
    REPO_ROOT / "outputs" / "role_research" / "validation_report.json",
    REPO_ROOT / "outputs" / "role_research" / "build_manifest.json",
    REPO_ROOT / "outputs" / "role_research" / "situational_player_week.csv.gz",
    REPO_ROOT / "outputs" / "role_research" / "game_player_usage.csv.gz",
    REPO_ROOT / "outputs" / "role_research" / "opportunity_events.csv.gz",
)

OPPORTUNITY_CONTEXT_PRESERVATION = {
    "publicExposure": False,
    "availableColumns": {
        "opportunityIdentity": [
            "season",
            "week",
            "game_id",
            "play_id",
            "team",
            "player_id",
            "opportunity_type",
        ],
        "opportunityKinds": ["carry", "target"],
        "retainedContext": [
            "normal_game",
            "early_down",
            "passing_down",
            "short_yardage",
            "two_minute",
            "red_zone",
            "inside_10",
            "inside_5",
            "end_zone",
            "leading",
            "trailing",
            "close",
            "quarter_1",
            "quarter_2",
            "quarter_3",
            "quarter_4",
        ],
        "completedTouches": ["receptions"],
        "playerSnapShare": ["snap_share"],
        "weeklyTeamStint": ["team"],
    },
    "sourceAvailableNotCommitted": ["yardline_100", "down", "ydstogo", "offense_snaps"],
    "notAuthoritativelyAvailable": [
        "team_offensive_snap_denominator",
        "goal_to_go",
        "transaction_timing",
        "head_coach",
        "offensive_coordinator",
        "play_caller",
        "quarterback_regime",
    ],
}


class DepthSnapExportError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistrySpec:
    publication_status: str
    season: int
    through_week: int | None
    generated_at: str
    source_version: str
    validation_result: str
    data_notice: str
    source_artifacts: tuple[Mapping[str, str], ...]
    formula_version: str | None = None
    pipeline_run_id: str | None = None
    status_payload: Mapping[str, Any] | None = None
    historical_parity: bool = False


@dataclass(frozen=True)
class PlannedBundle:
    family: str
    path: str
    bundle: Mapping[str, Any]
    record_count: int
    bundle_id: str | None = None


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def source_artifacts(paths: Iterable[Path]) -> tuple[Mapping[str, str], ...]:
    rows = []
    for path in sorted((Path(item) for item in paths), key=lambda item: _relative(item)):
        if not path.is_file():
            raise DepthSnapExportError(f"Required source artifact is missing: {_relative(path)}")
        rows.append({"path": _relative(path), "sha256": sha256_file(path)})
    return tuple(rows)


def content_addressed_source_version(
    *,
    season: int,
    publication_status: str,
    artifacts: Sequence[Mapping[str, str]],
) -> str:
    descriptor = {
        "publicationStatus": publication_status,
        "season": season,
        "sourceArtifacts": list(artifacts),
    }
    return f"sha256:{sha256_bytes(canonical_json_bytes(descriptor))}"


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise DepthSnapExportError(f"Could not read JSON artifact {_relative(path)}") from exc
    if not isinstance(value, dict):
        raise DepthSnapExportError(f"Expected an object in {_relative(path)}")
    return value


def active_registry_spec(generated_at: str | None = None) -> RegistrySpec:
    status = _load_json(ACTIVE_STATUS_PATH)
    python_state = str(status.get("status") or "")
    if python_state not in {"PRESEASON", "WAITING_FOR_COMPLETED_WEEK"}:
        raise DepthSnapExportError(
            f"Active status {python_state!r} is not a no-published-week state"
        )
    artifacts = source_artifacts([ACTIVE_STATUS_PATH])
    season = int(status["season"])
    return RegistrySpec(
        publication_status="no_published_week",
        season=season,
        through_week=None,
        generated_at=generated_at or utc_now(),
        source_version=content_addressed_source_version(
            season=season,
            publication_status="no_published_week",
            artifacts=artifacts,
        ),
        validation_result="pass",
        data_notice=str(status["message"]),
        source_artifacts=artifacts,
        status_payload=status,
    )


def historical_registry_spec(generated_at: str | None = None) -> RegistrySpec:
    artifacts = source_artifacts(HISTORICAL_SOURCE_PATHS)
    audit = _load_json(REPO_ROOT / "outputs" / "role_research" / "canonical_audit_2025.json")
    validation = _load_json(REPO_ROOT / "outputs" / "role_research" / "validation_report.json")
    if audit.get("status") != "PASS" or validation.get("status") != "PASS":
        raise DepthSnapExportError("Completed-2025 historical artifacts are not independently validated")
    if int(audit.get("season") or 0) != 2025:
        raise DepthSnapExportError("Historical parity registry must remain labeled season 2025")
    return RegistrySpec(
        publication_status="published",
        season=2025,
        through_week=18,
        generated_at=generated_at or utc_now(),
        source_version=content_addressed_source_version(
            season=2025,
            publication_status="published",
            artifacts=artifacts,
        ),
        validation_result="pass",
        data_notice=(
            "Temporary completed-2025 historical parity registry for Phase 4B "
            "verification; it is not the active 2026 publication."
        ),
        source_artifacts=artifacts,
        status_payload={"status": "PUBLISHED", "historicalParity": True},
        historical_parity=True,
    )


def current_published_registry_spec(
    status_path: Path = ACTIVE_STATUS_PATH,
    *,
    output_dir: Path = CURRENT_ROLE_OUTPUT_DIRECTORY,
    generated_at: str | None = None,
) -> RegistrySpec:
    status_path = Path(status_path)
    output_dir = Path(output_dir)
    status = _load_json(status_path)
    if status.get("status") != "PUBLISHED":
        raise DepthSnapExportError(
            "A populated current registry requires supplied PUBLISHED status"
        )
    season = int(status.get("season") or 0)
    through_week = int(status.get("published_through_week") or 0)
    if season < 2026 or not 1 <= through_week <= 18:
        raise DepthSnapExportError(
            "Current published status requires season 2026 or later and Week 1 through 18"
        )
    validation = validate_published_role_outputs(season, output_dir)
    if validation.get("status") != "PASS":
        raise DepthSnapExportError(
            "Current-season role outputs failed independent publication validation"
        )
    artifact_paths = [
        output_dir / f"canonical_role_{season}_live.csv.gz",
        output_dir / f"situational_player_week_{season}_live.csv.gz",
        output_dir / f"game_player_usage_{season}_live.csv.gz",
        output_dir / f"opportunity_events_{season}_live.csv.gz",
        output_dir / f"partial_game_status_{season}_live.csv.gz",
        output_dir / f"join_coverage_{season}_live.csv",
        output_dir / f"source_coverage_{season}_live.csv",
        output_dir / f"role_research_manifest_{season}.json",
        output_dir / f"role_research_validation_{season}.json",
        output_dir / f"role_research_status_{season}.json",
        output_dir / f"source_input_manifest_{season}_live.csv",
        output_dir / f"completion_gate_{season}.csv",
    ]
    if status_path.resolve() not in {
        path.resolve() for path in artifact_paths
    }:
        artifact_paths.append(status_path)
    artifacts = source_artifacts(artifact_paths)
    manifest = _load_json(output_dir / f"role_research_manifest_{season}.json")
    return RegistrySpec(
        publication_status="published",
        season=season,
        through_week=through_week,
        generated_at=generated_at or utc_now(),
        source_version=content_addressed_source_version(
            season=season,
            publication_status="published",
            artifacts=artifacts,
        ),
        validation_result="pass",
        data_notice=str(status.get("message") or f"Published through Week {through_week}."),
        source_artifacts=artifacts,
        formula_version=(
            str(manifest["formula_version"])
            if manifest.get("formula_version")
            else None
        ),
        pipeline_run_id=(
            str(status["staging_run_id"])
            if status.get("staging_run_id")
            else None
        ),
        status_payload=status,
    )


def registry_spec_from_status(
    status_path: Path,
    *,
    generated_at: str | None = None,
) -> RegistrySpec:
    status = _load_json(status_path)
    python_state = str(status.get("status") or "")
    mapping = {
        "PRESEASON": ("no_published_week", "pass"),
        "WAITING_FOR_COMPLETED_WEEK": ("no_published_week", "pass"),
        "BLOCKED": ("unavailable", "not_applicable"),
    }
    if python_state not in mapping:
        raise DepthSnapExportError(
            "Only non-published supplied operational states are accepted by this entrypoint"
        )
    publication_status, validation_result = mapping[python_state]
    artifacts = source_artifacts([status_path])
    season = int(status["season"])
    through_week = status.get("published_through_week")
    return RegistrySpec(
        publication_status=publication_status,
        season=season,
        through_week=int(through_week) if through_week is not None else None,
        generated_at=generated_at or utc_now(),
        source_version=content_addressed_source_version(
            season=season,
            publication_status=publication_status,
            artifacts=artifacts,
        ),
        validation_result=validation_result,
        data_notice=str(status.get("message") or "Publication metadata is unavailable."),
        source_artifacts=artifacts,
        status_payload=status,
    )


def _team_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for _, (team_id, name) in TEAM_VARIANTS.items():
        names.setdefault(team_id, name)
    if set(names) != set(TEAM_ALIGNMENT):
        missing = sorted(set(TEAM_ALIGNMENT) - set(names))
        extra = sorted(set(names) - set(TEAM_ALIGNMENT))
        raise DepthSnapExportError(
            f"Authoritative team crosswalk mismatch; missing={missing}, extra={extra}"
        )
    return names


def team_id(raw_team: object) -> str:
    value = canonical_team(raw_team)
    if value not in TEAM_ALIGNMENT:
        raise DepthSnapExportError(f"Unresolved evidence team: {raw_team!r}")
    return value


def build_team_identities() -> dict[str, Mapping[str, Any]]:
    names = _team_names()
    accents = ("teal", "amber", "slate")
    result = {}
    for index, abbreviation in enumerate(sorted(names)):
        conference, division = TEAM_ALIGNMENT[abbreviation]
        name = names[abbreviation]
        result[abbreviation] = {
            "id": abbreviation,
            "abbreviation": abbreviation,
            "name": name,
            "conference": conference,
            "division": division,
            "monogram": abbreviation,
            "accent": accents[index % len(accents)],
            "href": f"/teams/{abbreviation}",
            "searchAliases": [abbreviation, name],
        }
    return result


def _current_identity_rows(data: pd.DataFrame, season: int, through_week: int) -> pd.DataFrame:
    rows = data[
        data["season"].eq(season)
        & data["week"].le(through_week)
        & data["position"].isin(["RB", "WR", "TE"])
    ].copy()
    if rows.empty:
        raise DepthSnapExportError(f"No canonical player rows for {season}")
    rows["player_id"] = rows["player_id"].astype(str)
    return (
        rows.sort_values(["week", "team", "player_name"], kind="stable")
        .drop_duplicates("player_id", keep="last")
        .sort_values(["player_name", "player_id"], kind="stable")
        .reset_index(drop=True)
    )


def _player_identity(row: Mapping[str, Any]) -> Mapping[str, Any]:
    player_id = str(row["player_id"])
    return {
        "id": player_id,
        "name": str(row["player_name"]),
        "position": str(row["position"]),
        "href": f"/players/{player_id}",
        "searchAliases": [],
    }


def build_player_identities(
    data: pd.DataFrame,
    season: int,
    through_week: int,
) -> tuple[dict[str, Mapping[str, Any]], dict[str, str]]:
    identities: dict[str, Mapping[str, Any]] = {}
    current_teams: dict[str, str] = {}
    for row in _current_identity_rows(data, season, through_week).to_dict("records"):
        identity = _player_identity(row)
        player_id = str(identity["id"])
        identities[player_id] = identity
        current_teams[player_id] = team_id(row["team"])
    return identities, current_teams


def _common(spec: RegistrySpec, schema_version: str) -> dict[str, Any]:
    return {
        "schemaVersion": schema_version,
        "dataMode": "export",
        "dataNotice": spec.data_notice,
        "status": spec.publication_status,
        "season": spec.season,
        "throughWeek": spec.through_week,
        "generatedAt": spec.generated_at,
        "sourceVersion": spec.source_version,
    }


def _evidence(
    numerator: object,
    denominator: object,
    role_family: str,
) -> Mapping[str, Any]:
    raw = int(float(numerator))
    total = int(float(denominator))
    if total <= 0 or raw < 0 or raw > total:
        raise DepthSnapExportError(
            f"Invalid evidence counts for {role_family}: {raw}/{total}"
        )
    return {
        "numerator": raw,
        "denominator": total,
        "share": raw / total,
        "opportunityLabel": OPPORTUNITY_LABELS[role_family],
    }


def _movement(
    prior_raw: object,
    prior_denominator: object,
    current_raw: object,
    current_denominator: object,
    role_family: str,
) -> Mapping[str, Any]:
    previous = _evidence(prior_raw, prior_denominator, role_family)
    current = _evidence(current_raw, current_denominator, role_family)
    return {
        "previous": previous,
        "current": current,
        "percentagePointChange": (current["share"] - previous["share"]) * 100,
    }


def _quality_for_rows(rows: pd.DataFrame) -> tuple[str, str]:
    statuses = set(rows.get("partial_game_status", pd.Series(dtype=str)).dropna().astype(str))
    if "confirmed" in statuses:
        raise DepthSnapExportError("Confirmed partial-game evidence reached the public exporter")
    if "suspected_corroborated" in statuses:
        participation = "suspected_corroborated"
    elif "suspected_statistical" in statuses:
        participation = "suspected_statistical"
    else:
        participation = "complete"
    normal_denominator = pd.to_numeric(
        rows.get("team_opportunities_normal", pd.Series(dtype=float)),
        errors="coerce",
    )
    supporting = "available" if normal_denominator.fillna(0).gt(0).any() else "unavailable"
    return participation, supporting


def _window_weeks(
    season_rows: pd.DataFrame,
    through_week: int,
    window: int | str,
) -> list[int]:
    weeks = sorted(
        season_rows.loc[season_rows["week"].le(through_week), "week"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    return weeks if window == "Season" else weeks[-int(window) :]


def authoritative_report_rows(
    report_name: str,
    *,
    season: int,
    through_week: int,
    window: int | str,
    minimum_sample: int = MINIMUM_REPORT_SAMPLE,
) -> pd.DataFrame:
    families = list(REPORT_FAMILIES[report_name])
    all_play = league_window_summary(season, through_week, window, "All plays", families)
    if all_play.empty:
        return all_play
    rows = all_play[
        pd.to_numeric(all_play["raw_opportunities"], errors="coerce").ge(minimum_sample)
    ].copy()
    normal = league_window_summary(season, through_week, window, "Normal game", families)
    if normal.empty:
        rows["normal_raw"] = pd.NA
        rows["normal_denominator"] = pd.NA
        rows["normal_share"] = pd.NA
    else:
        normal = normal[
            [
                "player_id",
                "team",
                "role_family",
                "raw_opportunities",
                "team_denominator",
                "share",
            ]
        ].rename(
            columns={
                "raw_opportunities": "normal_raw",
                "team_denominator": "normal_denominator",
                "share": "normal_share",
            }
        )
        rows = rows.merge(normal, on=["player_id", "team", "role_family"], how="left")
    if report_name == "Role Movement":
        rows = rows[rows["change"].notna()].copy()
        rows["absolute_change"] = pd.to_numeric(rows["change"], errors="coerce").abs()
    return rows.sort_values(
        ["share", "raw_opportunities", "player_name"],
        ascending=[False, False, True],
        kind="stable",
    ).reset_index(drop=True)


def _period(
    label: str,
    weeks: Sequence[int],
) -> Mapping[str, Any]:
    if not weeks:
        raise DepthSnapExportError(f"Cannot build empty report period {label}")
    return {"label": label, "startWeek": min(weeks), "endWeek": max(weeks)}


def _report_view_option(
    *,
    view_id: str,
    label: str,
    current_weeks: Sequence[int],
    prior_weeks: Sequence[int],
    movement: bool,
) -> Mapping[str, Any]:
    option: dict[str, Any] = {
        "id": view_id,
        "label": label,
        "description": f"Python-supplied {label.lower()} view",
        "currentPeriod": _period(
            f"Weeks {min(current_weeks)}–{max(current_weeks)}", current_weeks
        ),
    }
    if movement and prior_weeks:
        option["priorPeriod"] = _period(
            f"Weeks {min(prior_weeks)}–{max(prior_weeks)}", prior_weeks
        )
    return option


def _row_quality(
    canonical: pd.DataFrame,
    row: Mapping[str, Any],
    weeks: Sequence[int],
    season: int,
) -> tuple[str, str]:
    matching = canonical[
        canonical["season"].eq(season)
        & canonical["week"].isin(list(weeks))
        & canonical["player_id"].astype(str).eq(str(row["player_id"]))
        & canonical["team"].astype(str).eq(str(row["team"]))
        & canonical["role_family"].eq(str(row["role_family"]))
    ]
    if matching.empty:
        raise DepthSnapExportError(
            f"Could not resolve quality rows for {row['player_id']} {row['role_family']}"
        )
    return _quality_for_rows(matching)


def _report_row(
    row: Mapping[str, Any],
    *,
    rank: int,
    view_id: str,
    movement_report: bool,
    players: Mapping[str, Mapping[str, Any]],
    teams: Mapping[str, Mapping[str, Any]],
    canonical: pd.DataFrame,
    weeks: Sequence[int],
    season: int,
) -> Mapping[str, Any]:
    player_id = str(row["player_id"])
    role_family = str(row["role_family"])
    evidence_team_id = team_id(row["team"])
    if player_id not in players:
        raise DepthSnapExportError(f"Unresolved player identity {player_id}")
    participation, supporting_status = _row_quality(
        canonical, row, weeks, season
    )
    base: dict[str, Any] = {
        "id": f"{player_id}-{evidence_team_id}-{role_family}-{view_id}",
        "authoritativeRank": rank,
        "player": players[player_id],
        "evidenceTeam": teams[evidence_team_id],
        "roleFamily": role_family,
        "roleLabel": ROLE_LABELS[role_family],
        "teamHref": teams[evidence_team_id]["href"],
        "playerHref": players[player_id]["href"],
        "evidenceHref": players[player_id]["href"],
        "participationQuality": participation,
        "supportingContextStatus": supporting_status,
    }
    if pd.notna(row.get("normal_denominator")) and float(row["normal_denominator"]) > 0:
        base["supportingContext"] = {
            "label": "Normal game",
            "evidence": _evidence(
                row["normal_raw"], row["normal_denominator"], role_family
            ),
        }
    if movement_report:
        movement = _movement(
            row["prior_raw"],
            row["prior_denom"],
            row["raw_opportunities"],
            row["team_denominator"],
            role_family,
        )
        points = float(movement["percentagePointChange"])
        direction = "gain" if points > 0 else "decline" if points < 0 else "stable"
        base.update(
            {
                "movement": movement,
                "direction": direction,
                "finding": (
                    f"{ROLE_LABELS[role_family]} moved "
                    f"{abs(points):.1f} percentage points "
                    f"{'higher' if points >= 0 else 'lower'} between the supplied periods."
                ),
            }
        )
    else:
        base["current"] = _evidence(
            row["raw_opportunities"], row["team_denominator"], role_family
        )
    return base


def _report_summary(
    report_name: str,
    rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    first = rows[0] if rows else None
    answer = (
        f"{len(rows)} rows are present in the supplied Python authority order."
        if first is None
        else (
            f"{first['player']['name']} is first in the supplied Python "
            f"{REPORT_TITLES[REPORT_PUBLIC_FAMILIES[report_name]]} order."
        )
    )
    team_count = len({row["evidenceTeam"]["id"] for row in rows})
    return {
        "answer": answer,
        "items": [
            {
                "label": "Rows",
                "value": str(len(rows)),
                "detail": "minimum eight supplied opportunities",
            },
            {
                "label": "Evidence teams",
                "value": str(team_count),
                "detail": "canonical evidence-team references",
            },
        ],
    }


def build_report_bundle(
    report_name: str,
    *,
    spec: RegistrySpec,
    players: Mapping[str, Mapping[str, Any]],
    teams: Mapping[str, Mapping[str, Any]],
    canonical: pd.DataFrame,
) -> tuple[Mapping[str, Any], dict[str, list[Mapping[str, Any]]]]:
    public_family = REPORT_PUBLIC_FAMILIES[report_name]
    bundle_family = REPORT_BUNDLE_FAMILIES[report_name]
    movement_report = report_name == "Role Movement"
    season_rows = canonical[canonical["season"].eq(spec.season)]
    all_weeks = _window_weeks(season_rows, int(spec.through_week), "Season")
    view_rows: dict[str, list[Mapping[str, Any]]] = {}
    available_views: list[Mapping[str, Any]] = []
    views: list[Mapping[str, Any]] = []
    for view_id, label, window in VIEW_WINDOWS:
        current_weeks = _window_weeks(season_rows, int(spec.through_week), window)
        prior_weeks = [week for week in all_weeks if week < min(current_weeks)]
        if window != "Season":
            prior_weeks = prior_weeks[-int(window) :]
        source_rows = authoritative_report_rows(
            report_name,
            season=spec.season,
            through_week=int(spec.through_week),
            window=window,
        )
        rows = [
            _report_row(
                row,
                rank=index,
                view_id=view_id,
                movement_report=movement_report,
                players=players,
                teams=teams,
                canonical=canonical,
                weeks=current_weeks,
                season=spec.season,
            )
            for index, row in enumerate(source_rows.to_dict("records"), 1)
        ]
        view_rows[view_id] = rows
        available_views.append(
            _report_view_option(
                view_id=view_id,
                label=label,
                current_weeks=current_weeks,
                prior_weeks=prior_weeks,
                movement=movement_report,
            )
        )
        views.append(
            {
                "viewId": view_id,
                "summary": _report_summary(report_name, rows),
                "rows": rows,
            }
        )
    default_rows = view_rows["last4"]
    available_sorts = [
        {"id": "authority", "label": "Authority"},
        {"id": "share", "label": "Current share"},
        {"id": "player", "label": "Player"},
        {"id": "team", "label": "Evidence team"},
    ]
    if movement_report:
        available_sorts = [
            {"id": "authority", "label": "Authority"},
            {"id": "gainers", "label": "Gainers"},
            {"id": "decliners", "label": "Decliners"},
            {"id": "absolute_change", "label": "Largest absolute change"},
            {"id": "player", "label": "Player"},
            {"id": "team", "label": "Evidence team"},
        ]
    schema_version = SCHEMA_VERSIONS[bundle_family]
    bundle = {
        **_common(spec, schema_version),
        "reportFamily": public_family,
        "title": report_name,
        "question": REPORT_DEFINITIONS[report_name],
        "description": (
            "Python-supplied membership and order with exact player counts and "
            "matching evidence-team denominators."
        ),
        "availableViews": available_views,
        "defaultView": "last4",
        "defaultSort": "authority",
        "availableSorts": available_sorts,
        "teamOptions": ["ALL", *sorted(teams)],
        "resultCount": len(default_rows),
        "views": views,
    }
    return bundle, view_rows


def _report_links() -> list[Mapping[str, Any]]:
    return [
        {
            "family": family,
            "label": REPORT_TITLES[family],
            "description": REPORT_DEFINITIONS[REPORT_TITLES[family]],
            "href": REPORT_PATHS[family],
        }
        for family in ("backfield_control", "target_hierarchy", "role_movement")
    ]


def _report_family_for_finding(category: str, role_family: str) -> str:
    if category in {CATEGORY_GAINED, CATEGORY_LOST}:
        return "role_movement"
    return (
        "backfield_control"
        if role_family.startswith("rb_")
        else "target_hierarchy"
    )


def _home_finding(
    row: Mapping[str, Any],
    *,
    index: int,
    players: Mapping[str, Mapping[str, Any]],
    teams: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    player_id = str(row["player_id"])
    role_family = str(row["role_family"])
    evidence_team_id = team_id(row["team"])
    participation = (
        "suspected_corroborated"
        if bool(row.get("suspected_partial_corroborated"))
        else "suspected_statistical"
        if bool(row.get("suspected_partial_game"))
        else "complete"
    )
    current = _evidence(
        row["current_raw"], row["current_denominator"], role_family
    )
    previous = _evidence(
        row["baseline_raw"], row["baseline_denominator"], role_family
    )
    return {
        "id": f"home-{index}-{player_id}-{role_family}",
        "kind": FINDING_KINDS[str(row["category"])],
        "reportFamily": _report_family_for_finding(str(row["category"]), role_family),
        "roleFamily": role_family,
        "roleLabel": ROLE_LABELS[role_family],
        "player": players[player_id],
        "evidenceTeam": teams[evidence_team_id],
        "headline": str(row["headline"]),
        "current": current,
        "movement": {
            "previous": previous,
            "current": current,
            "percentagePointChange": (current["share"] - previous["share"]) * 100,
        },
        "evidenceHref": players[player_id]["href"],
        "participationQuality": participation,
        "supportingContextStatus": "available",
    }


def _leaderboard_row(row: Mapping[str, Any], rank: int) -> Mapping[str, Any]:
    evidence = row["movement"]["current"] if "movement" in row else row["current"]
    movement_points = (
        float(row["movement"]["percentagePointChange"]) if "movement" in row else 0.0
    )
    return {
        "rank": rank,
        "player": row["player"],
        "evidenceTeam": row["evidenceTeam"],
        "evidence": evidence,
        "movementPoints": movement_points,
        "evidenceHref": row["evidenceHref"],
    }


def _team_snapshot(
    evidence_team: Mapping[str, Any],
    *,
    week: int,
    report_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Mapping[str, Any]:
    team_id_value = str(evidence_team["id"])
    backfield = [
        row
        for row in report_rows["backfield_control"]
        if row["evidenceTeam"]["id"] == team_id_value
    ][:2]
    target_rows = [
        row
        for row in report_rows["target_hierarchy"]
        if row["evidenceTeam"]["id"] == team_id_value
    ]
    wr = next((row for row in target_rows if row["player"]["position"] == "WR"), None)
    te = next((row for row in target_rows if row["player"]["position"] == "TE"), None)
    rows = []
    for index, row in enumerate(backfield):
        rows.append(
            {
                "role": f"RB{index + 1}",
                "player": row["player"]["name"],
                "evidence": row["current"],
                "tone": "lead" if index == 0 else "secondary",
            }
        )
    for role, row in (("WR1", wr), ("TE1", te)):
        if row:
            rows.append(
                {
                    "role": role,
                    "player": row["player"]["name"],
                    "evidence": row["current"],
                    "tone": "lead" if role == "WR1" else "secondary",
                }
            )
    movement = next(
        (
            row
            for row in report_rows["role_movement"]
            if row["evidenceTeam"]["id"] == team_id_value
        ),
        None,
    )
    snapshot: dict[str, Any] = {
        "monogram": evidence_team["monogram"],
        "teamName": evidence_team["name"],
        "teamCode": team_id_value,
        "week": week,
        "rows": rows,
        "reportHref": evidence_team["href"],
    }
    if movement:
        snapshot["biggestMovement"] = {
            "player": movement["player"]["name"],
            "summary": movement["roleLabel"],
            "percentagePointChange": movement["movement"]["percentagePointChange"],
            "evidenceHref": movement["evidenceHref"],
        }
    return snapshot


def build_home_bundle(
    *,
    spec: RegistrySpec,
    players: Mapping[str, Mapping[str, Any]],
    teams: Mapping[str, Mapping[str, Any]],
    report_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    canonical: pd.DataFrame,
) -> Mapping[str, Any]:
    available = sorted(
        canonical.loc[canonical["season"].eq(spec.season), "week"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    home_week = default_home_week(spec.season, available)
    if home_week is None:
        raise DepthSnapExportError("Historical parity Home feed has no available week")
    cards, _ = build_weekly_role_report(spec.season, home_week)
    if cards.empty:
        raise DepthSnapExportError("Authoritative weekly report returned no Home findings")
    findings = [
        _home_finding(
            row,
            index=index,
            players=players,
            teams=teams,
        )
        for index, row in enumerate(cards.to_dict("records"), 1)
    ]
    lead = findings[0]
    leaderboard = {
        family: [
            _leaderboard_row(row, rank)
            for rank, row in enumerate(report_rows[family][:3], 1)
        ]
        for family in ("backfield_control", "target_hierarchy", "role_movement")
    }
    return {
        **_common(spec, SCHEMA_VERSIONS["home"]),
        "reportLinks": _report_links(),
        "leadFinding": lead,
        "findings": findings[1:],
        "teamSnapshot": _team_snapshot(
            lead["evidenceTeam"], week=home_week, report_rows=report_rows
        ),
        "reportLeaderboard": leaderboard,
    }


def _hierarchy_record(row: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "authoritativeOrder": row["authoritativeRank"],
        "player": row["player"],
        "evidenceTeam": row["evidenceTeam"],
        "roleFamily": row["roleFamily"],
        "roleLabel": row["roleLabel"],
        "evidence": row["current"],
        "participationQuality": row["participationQuality"],
        "supportingContextStatus": row["supportingContextStatus"],
    }


def _movement_record(row: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "authoritativeOrder": row["authoritativeRank"],
        "player": row["player"],
        "evidenceTeam": row["evidenceTeam"],
        "reportFamily": "role_movement",
        "roleFamily": row["roleFamily"],
        "roleLabel": row["roleLabel"],
        "movement": row["movement"],
        "direction": row["direction"],
        "finding": row["finding"],
        "reportHref": REPORT_PATHS["role_movement"],
        "participationQuality": row["participationQuality"],
        "supportingContextStatus": row["supportingContextStatus"],
    }


def _membership(family: str, rank: int) -> Mapping[str, Any]:
    return {
        "family": family,
        "label": REPORT_TITLES[family],
        "href": REPORT_PATHS[family],
        "authoritativeRank": rank,
    }


def _quality_for_canonical_row(row: Mapping[str, Any]) -> tuple[str, str]:
    status = str(row.get("partial_game_status") or "none")
    if status == "confirmed":
        raise DepthSnapExportError("Confirmed partial row reached player chronology")
    participation = (
        status
        if status in {"suspected_statistical", "suspected_corroborated"}
        else "complete"
    )
    normal_denominator = int(float(row.get("team_opportunities_normal") or 0))
    return participation, "available" if normal_denominator > 0 else "unavailable"


def build_identity_bundles(
    *,
    spec: RegistrySpec,
    players: Mapping[str, Mapping[str, Any]],
    current_teams: Mapping[str, str],
    teams: Mapping[str, Mapping[str, Any]],
    report_views: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    canonical: pd.DataFrame,
) -> tuple[
    list[Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    list[Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    list[Mapping[str, Any]],
]:
    default_current = [
        *report_views["backfield_control"]["last4"],
        *report_views["target_hierarchy"]["last4"],
    ]
    default_movements = list(report_views["role_movement"]["last4"])
    team_bundles: dict[str, Mapping[str, Any]] = {}
    team_directory: list[Mapping[str, Any]] = []
    for evidence_team_id, team in sorted(teams.items()):
        backfield = [
            _hierarchy_record(row)
            for row in report_views["backfield_control"]["last4"]
            if row["evidenceTeam"]["id"] == evidence_team_id
        ]
        targets = [
            row
            for row in report_views["target_hierarchy"]["last4"]
            if row["evidenceTeam"]["id"] == evidence_team_id
        ]
        wr = [
            _hierarchy_record(row)
            for row in targets
            if row["player"]["position"] == "WR"
        ]
        te = [
            _hierarchy_record(row)
            for row in targets
            if row["player"]["position"] == "TE"
        ]
        movements = [
            _movement_record(row)
            for row in default_movements
            if row["evidenceTeam"]["id"] == evidence_team_id
        ]
        linked_ids = sorted(
            {
                row["player"]["id"]
                for row in [*backfield, *wr, *te, *movements]
            }
        )
        linked_players = [players[player_id] for player_id in linked_ids]
        bundle = {
            **_common(spec, SCHEMA_VERSIONS["team"]),
            "team": team,
            "backfieldHierarchy": backfield,
            "wrTargetHierarchy": wr,
            "teTargetHierarchy": te,
            "movements": movements,
            "linkedPlayers": linked_players,
            "availableViews": [view_id for view_id, _, _ in VIEW_WINDOWS],
        }
        team_bundles[evidence_team_id] = bundle
        team_directory.append(
            {
                "team": team,
                **({"topBackfield": backfield[0]} if backfield else {}),
                **({"topWr": wr[0]} if wr else {}),
                **({"topTe": te[0]} if te else {}),
                **({"largestMovement": movements[0]} if movements else {}),
            }
        )

    player_bundles: dict[str, Mapping[str, Any]] = {}
    player_directory: list[Mapping[str, Any]] = []
    canonical_season = canonical[
        canonical["season"].eq(spec.season)
        & canonical["week"].le(int(spec.through_week))
    ].copy()
    for player_id, player in sorted(players.items(), key=lambda item: (item[1]["name"], item[0])):
        current_team = teams[current_teams[player_id]]
        current_candidates = [
            row for row in default_current if row["player"]["id"] == player_id
        ]
        movement_candidates = [
            row for row in default_movements if row["player"]["id"] == player_id
        ]
        current_row = current_candidates[0] if current_candidates else None
        latest_movement = movement_candidates[0] if movement_candidates else None
        memberships = []
        for family, rows in (
            ("backfield_control", report_views["backfield_control"]["last4"]),
            ("target_hierarchy", report_views["target_hierarchy"]["last4"]),
            ("role_movement", report_views["role_movement"]["last4"]),
        ):
            match = next((row for row in rows if row["player"]["id"] == player_id), None)
            if match:
                memberships.append(_membership(family, int(match["authoritativeRank"])))
        weekly = []
        player_rows = canonical_season[
            canonical_season["player_id"].astype(str).eq(player_id)
        ].sort_values(["week", "role_family", "team"], kind="stable")
        for row in player_rows.to_dict("records"):
            participation, supporting = _quality_for_canonical_row(row)
            role_family = str(row["role_family"])
            weekly.append(
                {
                    "week": int(row["week"]),
                    "periodLabel": f"Week {int(row['week'])}",
                    "evidenceTeam": teams[team_id(row["team"])],
                    "roleFamily": role_family,
                    "roleLabel": ROLE_LABELS[role_family],
                    "evidence": _evidence(
                        row["raw_opportunities_all"],
                        row["team_opportunities_all"],
                        role_family,
                    ),
                    "opportunityLabel": OPPORTUNITY_LABELS[role_family],
                    "participationQuality": participation,
                    "supportingContextStatus": supporting,
                }
            )
        period_summaries = []
        for family in ("backfield_control", "target_hierarchy"):
            for view_id, _, _ in VIEW_WINDOWS:
                for row in report_views[family][view_id]:
                    if row["player"]["id"] == player_id:
                        period_summaries.append(
                            {
                                "label": f"{REPORT_TITLES[family]} · {view_id}",
                                "evidenceTeam": row["evidenceTeam"],
                                "roleFamily": row["roleFamily"],
                                "roleLabel": row["roleLabel"],
                                "evidence": row["current"],
                            }
                        )
        movement_history = []
        for view_id, _, _ in VIEW_WINDOWS:
            movement_history.extend(
                _movement_record(row)
                for row in report_views["role_movement"][view_id]
                if row["player"]["id"] == player_id
            )
        hierarchy_context = []
        if current_row:
            hierarchy_context = [
                _hierarchy_record(row)
                for row in default_current
                if row["evidenceTeam"]["id"] == current_row["evidenceTeam"]["id"]
                and row["player"]["position"] == player["position"]
            ]
        bundle: dict[str, Any] = {
            **_common(spec, SCHEMA_VERSIONS["player"]),
            "player": player,
            "currentTeam": current_team,
            "reportMemberships": memberships,
            "weeklyEvidence": weekly,
            "periodSummaries": period_summaries,
            "movementHistory": movement_history,
            "teamHierarchyContext": hierarchy_context,
        }
        if current_row:
            bundle.update(
                {
                    "currentEvidence": current_row["current"],
                    "currentEvidenceTeam": current_row["evidenceTeam"],
                    "currentRoleFamily": current_row["roleFamily"],
                    "currentRoleLabel": current_row["roleLabel"],
                }
            )
            if current_row.get("supportingContext"):
                bundle["supportingContext"] = current_row["supportingContext"]
        if latest_movement:
            bundle["latestMovement"] = _movement_record(latest_movement)
        player_bundles[player_id] = bundle
        directory: dict[str, Any] = {
            "player": player,
            "currentTeam": current_team,
            "memberships": memberships,
        }
        if current_row:
            directory.update(
                {
                    "currentEvidence": current_row["current"],
                    "currentEvidenceTeam": current_row["evidenceTeam"],
                    "roleFamily": current_row["roleFamily"],
                    "roleLabel": current_row["roleLabel"],
                }
            )
        if latest_movement:
            directory["latestMovement"] = _movement_record(latest_movement)
        player_directory.append(directory)

    search = [
        *[
            {
                "type": "team",
                "id": f"search-team-{record['team']['id']}",
                "displayName": record["team"]["name"],
                "secondaryLabel": f"Team · {record['team']['id']}",
                "summary": "Canonical team identity with structured role evidence.",
                "href": record["team"]["href"],
                "searchAliases": record["team"]["searchAliases"],
            }
            for record in team_directory
        ],
        *[
            {
                "type": "player",
                "id": f"search-player-{record['player']['id']}",
                "displayName": record["player"]["name"],
                "secondaryLabel": (
                    f"{record['player']['position']} · {record['currentTeam']['id']}"
                ),
                "summary": (
                    f"{record['currentEvidence']['numerator']} of "
                    f"{record['currentEvidence']['denominator']} "
                    f"{record['currentEvidence']['opportunityLabel']}"
                    if record.get("currentEvidence")
                    else "Stable player identity; no default-report evidence row."
                ),
                "href": record["player"]["href"],
                "searchAliases": record["player"]["searchAliases"],
            }
            for record in player_directory
        ],
    ]
    return team_directory, team_bundles, player_directory, player_bundles, search


def _status_checks(
    spec: RegistrySpec,
    *,
    bundle_count: int,
    players: int,
    teams: int,
    historical_audit: Mapping[str, Any] | None = None,
) -> list[Mapping[str, Any]]:
    checks: list[Mapping[str, Any]] = [
        {
            "id": "manifest-integrity",
            "label": "Manifest integrity",
            "status": "pass",
            "detail": "Every required bundle passed Python schema, hash, and record-count validation.",
            "required": True,
            "blocking": True,
            "numerator": bundle_count,
            "denominator": bundle_count,
            "percentage": 100,
        },
        {
            "id": "source-artifacts",
            "label": "Source artifact hashes",
            "status": "pass",
            "detail": "The source version addresses every exact artifact used by this registry.",
            "required": True,
            "blocking": True,
            "numerator": len(spec.source_artifacts),
            "denominator": len(spec.source_artifacts),
            "percentage": 100,
        },
    ]
    if spec.publication_status == "published":
        checks.extend(
            [
                {
                    "id": "identity-references",
                    "label": "Canonical identity references",
                    "status": "pass",
                    "detail": "All team-neutral players and row-level evidence teams resolve.",
                    "required": True,
                    "blocking": True,
                    "numerator": players + teams,
                    "denominator": players + teams,
                    "percentage": 100,
                },
                {
                    "id": "confirmed-partial-policy",
                    "label": "Confirmed partial-game exclusion",
                    "status": "pass",
                    "detail": "Confirmed partial-game family rows remain excluded by Python.",
                    "required": True,
                    "blocking": True,
                    "numerator": int(
                        (historical_audit or {}).get("confirmed_partial_family_rows", 0)
                    ),
                    "denominator": int(
                        (historical_audit or {}).get("confirmed_partial_family_rows", 0)
                    ),
                    "percentage": 100,
                },
                {
                    "id": "suspected-participation-quality",
                    "label": "Suspected participation quality retained",
                    "status": "pass",
                    "detail": "Suspected statistical and corroborated rows retain their supplied quality.",
                    "required": True,
                    "blocking": True,
                    "numerator": int(
                        (historical_audit or {}).get("suspected_partial_family_rows", 0)
                    ),
                    "denominator": int(
                        (historical_audit or {}).get("suspected_partial_family_rows", 0)
                    ),
                    "percentage": 100,
                },
            ]
        )
    else:
        checks.append(
            {
                "id": "publication-evidence",
                "label": "Publication evidence",
                "status": (
                    "reviewed"
                    if spec.publication_status == "no_published_week"
                    else "not_applicable"
                ),
                "detail": (
                    "No completed validated week is published; every evidence collection is empty."
                    if spec.publication_status == "no_published_week"
                    else "The supplied blocked state publishes no role evidence."
                ),
                "required": True,
                "blocking": True,
            }
        )
    return checks


def _limitations(spec: RegistrySpec) -> list[str]:
    limitations = [
        "DepthSnap is descriptive and does not provide projections, recommendations, odds, or picks.",
        "Opportunity Context raw source dimensions remain private and are not added to V1 public JSON.",
        "Team offensive-snap denominators, coaching chronology, play-caller chronology, and transaction timing are not authoritatively available.",
    ]
    if spec.historical_parity:
        limitations.insert(
            0,
            "This completed-2025 registry is temporary parity/review evidence and must not be promoted as the active 2026 registry.",
        )
    if spec.publication_status != "published":
        limitations.insert(
            0,
            "No player, team, report, movement, hierarchy, or weekly evidence row is published in this state.",
        )
    return limitations


def _status_bundle(
    spec: RegistrySpec,
    *,
    bundle_count: int,
    players: int,
    teams: int,
    historical_audit: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    checks = _status_checks(
        spec,
        bundle_count=bundle_count,
        players=players,
        teams=teams,
        historical_audit=historical_audit,
    )
    bundle: dict[str, Any] = {
        **_common(spec, SCHEMA_VERSIONS["status"]),
        "manifestSchemaVersion": "depthsnap.manifest.v1",
        "bundleCount": bundle_count,
        "validationSummary": (
            f"{bundle_count} required export bundles passed Python validation."
        ),
        "checks": checks,
        "limitations": _limitations(spec),
    }
    if spec.formula_version:
        bundle["formulaVersion"] = spec.formula_version
    if spec.pipeline_run_id:
        bundle["pipelineRunId"] = spec.pipeline_run_id
    return bundle


def _nonpublished_report(
    report_name: str,
    spec: RegistrySpec,
) -> Mapping[str, Any]:
    family = REPORT_PUBLIC_FAMILIES[report_name]
    bundle_family = REPORT_BUNDLE_FAMILIES[report_name]
    season_weeks = list(range(1, 19))
    views = []
    for view_id, label, window in VIEW_WINDOWS:
        width = 18 if window == "Season" else int(window)
        current_weeks = season_weeks[-width:]
        prior_weeks = season_weeks[: -width][-width:]
        views.append(
            _report_view_option(
                view_id=view_id,
                label=label,
                current_weeks=current_weeks,
                prior_weeks=prior_weeks,
                movement=report_name == "Role Movement",
            )
        )
    return {
        **_common(spec, SCHEMA_VERSIONS[bundle_family]),
        "reportFamily": family,
        "title": report_name,
        "question": REPORT_DEFINITIONS[report_name],
        "description": (
            "No evidence is supplied until a completed week passes every Python gate."
        ),
        "availableViews": views,
        "defaultView": "last4",
        "defaultSort": "authority",
        "availableSorts": [
            {"id": "authority", "label": "Authority"},
            {"id": "player", "label": "Player"},
            {"id": "team", "label": "Evidence team"},
        ],
        "teamOptions": [],
        "resultCount": 0,
        "views": [],
        "stateTitle": (
            "No completed week is published for this report"
            if spec.publication_status == "no_published_week"
            else "This report is unavailable"
        ),
        "stateMessage": spec.data_notice,
    }


def build_nonpublished_plan(spec: RegistrySpec) -> list[PlannedBundle]:
    if spec.publication_status not in {"no_published_week", "unavailable"}:
        raise DepthSnapExportError("Non-published plan received a published state")
    home = {
        **_common(spec, SCHEMA_VERSIONS["home"]),
        "reportLinks": _report_links(),
        "stateTitle": (
            "No completed week is published yet"
            if spec.publication_status == "no_published_week"
            else "Role data is unavailable"
        ),
        "stateMessage": spec.data_notice,
    }
    reports = {
        name: _nonpublished_report(name, spec)
        for name in ("Backfield Control", "Target Hierarchy", "Role Movement")
    }
    plan = [
        PlannedBundle("home", "home.json", home, 0),
        PlannedBundle(
            "reports_index",
            "reports/index.json",
            {
                **_common(spec, SCHEMA_VERSIONS["reports_index"]),
                "modules": [],
            },
            0,
        ),
        PlannedBundle(
            "report_backfield",
            "reports/backfield.json",
            reports["Backfield Control"],
            0,
        ),
        PlannedBundle(
            "report_targets",
            "reports/targets.json",
            reports["Target Hierarchy"],
            0,
        ),
        PlannedBundle(
            "report_movement",
            "reports/movement.json",
            reports["Role Movement"],
            0,
        ),
        PlannedBundle(
            "teams_index",
            "teams/index.json",
            {**_common(spec, SCHEMA_VERSIONS["teams_index"]), "teams": []},
            0,
        ),
        PlannedBundle(
            "players_index",
            "players/index.json",
            {
                **_common(spec, SCHEMA_VERSIONS["players_index"]),
                "players": [],
                "teamOptions": [],
            },
            0,
        ),
        PlannedBundle(
            "search",
            "search.json",
            {**_common(spec, SCHEMA_VERSIONS["search"]), "records": []},
            0,
        ),
    ]
    bundle_count = len(plan) + 1
    status = _status_bundle(
        spec, bundle_count=bundle_count, players=0, teams=0
    )
    plan.append(
        PlannedBundle(
            "status", "status.json", status, len(status["checks"])
        )
    )
    return plan


def build_published_plan(spec: RegistrySpec) -> list[PlannedBundle]:
    if spec.publication_status != "published" or spec.through_week is None:
        raise DepthSnapExportError(
            "Populated generation requires independently validated published inputs"
        )
    canonical = primary_rows(load_role_data())
    canonical = canonical[canonical["season"].eq(spec.season)].copy()
    if canonical.empty:
        raise DepthSnapExportError(
            f"No validated canonical rows are available for season {spec.season}"
        )
    observed_weeks = sorted(
        canonical["week"].dropna().astype(int).unique().tolist()
    )
    if not observed_weeks or observed_weeks[-1] != spec.through_week:
        raise DepthSnapExportError(
            "Canonical role rows do not reach the supplied published week"
        )
    teams = build_team_identities()
    players, current_teams = build_player_identities(
        canonical, spec.season, spec.through_week
    )
    report_bundles: dict[str, Mapping[str, Any]] = {}
    report_views: dict[str, Mapping[str, Sequence[Mapping[str, Any]]]] = {}
    for report_name in ("Backfield Control", "Target Hierarchy", "Role Movement"):
        bundle, views = build_report_bundle(
            report_name,
            spec=spec,
            players=players,
            teams=teams,
            canonical=canonical,
        )
        family = REPORT_PUBLIC_FAMILIES[report_name]
        report_bundles[family] = bundle
        report_views[family] = views
    default_rows = {
        family: report_views[family]["last4"]
        for family in ("backfield_control", "target_hierarchy", "role_movement")
    }
    home = build_home_bundle(
        spec=spec,
        players=players,
        teams=teams,
        report_rows=default_rows,
        canonical=canonical,
    )
    modules = []
    for family in ("backfield_control", "target_hierarchy", "role_movement"):
        rows = default_rows[family]
        if not rows:
            continue
        modules.append(
            {
                "kind": "movement" if family == "role_movement" else "current",
                "family": family,
                "title": REPORT_TITLES[family],
                "question": REPORT_DEFINITIONS[REPORT_TITLES[family]],
                "description": (
                    "First row from the supplied Python default report order."
                ),
                "href": REPORT_PATHS[family],
                "row": rows[0],
            }
        )
    team_directory, team_bundles, player_directory, player_bundles, search = (
        build_identity_bundles(
            spec=spec,
            players=players,
            current_teams=current_teams,
            teams=teams,
            report_views=report_views,
            canonical=canonical,
        )
    )
    plan: list[PlannedBundle] = [
        PlannedBundle("home", "home.json", home, 1 + len(home["findings"])),
        PlannedBundle(
            "reports_index",
            "reports/index.json",
            {
                **_common(spec, SCHEMA_VERSIONS["reports_index"]),
                "modules": modules,
            },
            len(modules),
        ),
        PlannedBundle(
            "report_backfield",
            "reports/backfield.json",
            report_bundles["backfield_control"],
            sum(len(view["rows"]) for view in report_bundles["backfield_control"]["views"]),
        ),
        PlannedBundle(
            "report_targets",
            "reports/targets.json",
            report_bundles["target_hierarchy"],
            sum(len(view["rows"]) for view in report_bundles["target_hierarchy"]["views"]),
        ),
        PlannedBundle(
            "report_movement",
            "reports/movement.json",
            report_bundles["role_movement"],
            sum(len(view["rows"]) for view in report_bundles["role_movement"]["views"]),
        ),
        PlannedBundle(
            "teams_index",
            "teams/index.json",
            {
                **_common(spec, SCHEMA_VERSIONS["teams_index"]),
                "teams": team_directory,
            },
            len(team_directory),
        ),
    ]
    plan.extend(
        PlannedBundle(
            "team",
            f"teams/{bundle_id}.json",
            bundle,
            len(bundle["linkedPlayers"]),
            bundle_id=bundle_id,
        )
        for bundle_id, bundle in sorted(team_bundles.items())
    )
    plan.append(
        PlannedBundle(
            "players_index",
            "players/index.json",
            {
                **_common(spec, SCHEMA_VERSIONS["players_index"]),
                "players": player_directory,
                "teamOptions": sorted(teams),
            },
            len(player_directory),
        )
    )
    plan.extend(
        PlannedBundle(
            "player",
            f"players/{bundle_id}.json",
            bundle,
            len(bundle["weeklyEvidence"]),
            bundle_id=bundle_id,
        )
        for bundle_id, bundle in sorted(player_bundles.items())
    )
    plan.append(
        PlannedBundle(
            "search",
            "search.json",
            {**_common(spec, SCHEMA_VERSIONS["search"]), "records": search},
            len(search),
        )
    )
    bundle_count = len(plan) + 1
    audit = {
        "confirmed_partial_family_rows": int(
            canonical.get(
                "confirmed_partial_game",
                pd.Series(False, index=canonical.index),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "suspected_partial_family_rows": int(
            canonical.get(
                "suspected_partial_game",
                pd.Series(False, index=canonical.index),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
    }
    status = _status_bundle(
        spec,
        bundle_count=bundle_count,
        players=len(players),
        teams=len(teams),
        historical_audit=audit,
    )
    plan.append(
        PlannedBundle(
            "status", "status.json", status, len(status["checks"])
        )
    )
    return plan


def build_plan(spec: RegistrySpec) -> list[PlannedBundle]:
    if spec.publication_status == "published":
        return build_published_plan(spec)
    return build_nonpublished_plan(spec)


def _record_count(family: str, bundle: Mapping[str, Any]) -> int:
    if family == "home":
        return (
            1 + len(bundle["findings"])
            if bundle["status"] == "published"
            else 0
        )
    if family == "reports_index":
        return len(bundle["modules"])
    if family.startswith("report_"):
        return sum(len(view["rows"]) for view in bundle["views"])
    if family == "teams_index":
        return len(bundle["teams"])
    if family == "team":
        return len(bundle["linkedPlayers"])
    if family == "players_index":
        return len(bundle["players"])
    if family == "player":
        return len(bundle["weeklyEvidence"])
    if family == "search":
        return len(bundle["records"])
    return len(bundle["checks"])


def write_registry(
    target: Path,
    spec: RegistrySpec,
    *,
    replace: bool = False,
) -> Mapping[str, Any]:
    target = Path(target).resolve()
    if target.exists():
        if not replace:
            raise DepthSnapExportError(f"Target already exists: {target}")
        _safe_rmtree(target, allowed_parent=target.parent)
    target.mkdir(parents=True)
    entries = []
    for item in build_plan(spec):
        if item.record_count != _record_count(item.family, item.bundle):
            raise DepthSnapExportError(
                f"Planned record count mismatch for {item.family}:{item.bundle_id or ''}"
            )
        destination = target.joinpath(*item.path.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_json_bytes(item.bundle)
        destination.write_bytes(payload)
        entries.append(
            {
                "family": item.family,
                **({"id": item.bundle_id} if item.bundle_id else {}),
                "path": item.path,
                "schemaVersion": SCHEMA_VERSIONS[item.family],
                "sha256": sha256_bytes(payload),
                "required": True,
                "recordCount": item.record_count,
            }
        )
    manifest: dict[str, Any] = {
        "schemaVersion": "depthsnap.manifest.v1",
        "productId": "depthsnap",
        "dataMode": "export",
        "publicationStatus": spec.publication_status,
        "validationResult": spec.validation_result,
        "season": spec.season,
        "throughWeek": spec.through_week,
        "generatedAt": spec.generated_at,
        "sourceVersion": spec.source_version,
        "entries": entries,
    }
    if spec.formula_version:
        manifest["formulaVersion"] = spec.formula_version
    if spec.pipeline_run_id:
        manifest["pipelineRunId"] = spec.pipeline_run_id
    (target / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    result = validate_registry(target)
    if result["publicationStatus"] != spec.publication_status:
        raise DepthSnapExportError("Validated publication state changed unexpectedly")
    return result


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _validate_evidence(value: Mapping[str, Any]) -> None:
    numerator = value.get("numerator")
    denominator = value.get("denominator")
    share = value.get("share")
    if not (
        isinstance(numerator, int)
        and isinstance(denominator, int)
        and denominator > 0
        and 0 <= numerator <= denominator
        and isinstance(share, (int, float))
        and abs(float(share) - numerator / denominator) <= 0.0005
    ):
        raise DepthSnapExportError(f"Invalid raw-share evidence: {value}")


def _expected_path(entry: Mapping[str, Any]) -> str:
    family = entry["family"]
    if family == "team":
        return f"teams/{entry['id']}.json"
    if family == "player":
        return f"players/{entry['id']}.json"
    return {
        "home": "home.json",
        "reports_index": "reports/index.json",
        "report_backfield": "reports/backfield.json",
        "report_targets": "reports/targets.json",
        "report_movement": "reports/movement.json",
        "teams_index": "teams/index.json",
        "players_index": "players/index.json",
        "search": "search.json",
        "status": "status.json",
    }[family]


def validate_registry(directory: Path) -> Mapping[str, Any]:
    directory = Path(directory).resolve()
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise DepthSnapExportError("Registry manifest is missing")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest_bytes != canonical_json_bytes(manifest):
        raise DepthSnapExportError("Manifest serialization is not deterministic")
    if manifest.get("schemaVersion") != "depthsnap.manifest.v1":
        raise DepthSnapExportError("Unsupported manifest schema")
    if manifest.get("dataMode") != "export":
        raise DepthSnapExportError("Python exporter emitted a non-export manifest")
    if manifest.get("publicationStatus") not in {
        "published",
        "no_published_week",
        "unavailable",
    }:
        raise DepthSnapExportError("Unsupported publication state")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise DepthSnapExportError("Manifest entries are missing")
    keys = [(entry["family"], entry.get("id")) for entry in entries]
    if len(keys) != len(set(keys)):
        raise DepthSnapExportError("Duplicate manifest entry")
    bundles: dict[tuple[str, str | None], Mapping[str, Any]] = {}
    for entry in entries:
        family = str(entry["family"])
        if family not in SCHEMA_VERSIONS:
            raise DepthSnapExportError(f"Unknown bundle family {family}")
        if entry.get("path") != _expected_path(entry):
            raise DepthSnapExportError(f"Non-canonical path for {family}")
        if entry.get("schemaVersion") != SCHEMA_VERSIONS[family]:
            raise DepthSnapExportError(f"Schema mismatch for {family}")
        path = directory.joinpath(*str(entry["path"]).split("/"))
        if not path.is_file():
            raise DepthSnapExportError(f"Missing bundle {entry['path']}")
        payload = path.read_bytes()
        if sha256_bytes(payload) != entry.get("sha256"):
            raise DepthSnapExportError(f"Hash mismatch for {entry['path']}")
        bundle = json.loads(payload)
        if payload != canonical_json_bytes(bundle):
            raise DepthSnapExportError(f"Non-deterministic serialization for {entry['path']}")
        if bundle.get("schemaVersion") != SCHEMA_VERSIONS[family]:
            raise DepthSnapExportError(f"Bundle schema mismatch for {entry['path']}")
        if bundle.get("dataMode") != "export":
            raise DepthSnapExportError(f"Bundle mode mismatch for {entry['path']}")
        if _record_count(family, bundle) != entry.get("recordCount"):
            raise DepthSnapExportError(f"Record-count mismatch for {entry['path']}")
        for candidate in _walk(bundle):
            if (
                isinstance(candidate, dict)
                and {"numerator", "denominator", "share", "opportunityLabel"}
                <= set(candidate)
            ):
                _validate_evidence(candidate)
        bundles[(family, entry.get("id"))] = bundle
    for family in (
        "home",
        "reports_index",
        "report_backfield",
        "report_targets",
        "report_movement",
        "teams_index",
        "players_index",
        "search",
        "status",
    ):
        if (family, None) not in bundles:
            raise DepthSnapExportError(f"Required family missing: {family}")
    status = bundles[("status", None)]
    common_keys = ("status", "season", "throughWeek", "generatedAt", "sourceVersion")
    expected_common = {
        "status": manifest["publicationStatus"],
        "season": manifest["season"],
        "throughWeek": manifest["throughWeek"],
        "generatedAt": manifest["generatedAt"],
        "sourceVersion": manifest["sourceVersion"],
    }
    if status.get("bundleCount") != len(entries):
        raise DepthSnapExportError("Status bundle count mismatch")
    for bundle in bundles.values():
        if any(bundle.get(key) != expected_common[key] for key in common_keys):
            raise DepthSnapExportError("Registry-wide publication metadata mismatch")
    team_ids = {
        bundle["team"]["id"]
        for (family, _), bundle in bundles.items()
        if family == "team"
    }
    player_ids = {
        bundle["player"]["id"]
        for (family, _), bundle in bundles.items()
        if family == "player"
    }
    for bundle in bundles.values():
        for candidate in _walk(bundle):
            if not isinstance(candidate, dict):
                continue
            if "player" in candidate and isinstance(candidate["player"], dict):
                player = candidate["player"]
                if set(player) - {
                    "id",
                    "name",
                    "position",
                    "href",
                    "jerseyNumber",
                    "searchAliases",
                }:
                    raise DepthSnapExportError("Player identity is not team-neutral")
                if player_ids and player.get("id") not in player_ids:
                    raise DepthSnapExportError("Unresolved player reference")
            for key in ("evidenceTeam", "currentTeam", "currentEvidenceTeam"):
                if key in candidate:
                    team = candidate[key]
                    if not isinstance(team, dict) or (
                        team_ids and team.get("id") not in team_ids
                    ):
                        raise DepthSnapExportError("Unresolved evidence-team reference")
    if manifest["publicationStatus"] != "published":
        if any(family in {"team", "player"} for family, _ in bundles):
            raise DepthSnapExportError("Non-published registry contains identity dossiers")
        if any(
            bundle.get("modules")
            or bundle.get("teams")
            or bundle.get("players")
            or bundle.get("records")
            or bundle.get("views")
            for bundle in bundles.values()
        ):
            raise DepthSnapExportError("Non-published registry contains public evidence")
    return {
        "publicationStatus": manifest["publicationStatus"],
        "season": manifest["season"],
        "throughWeek": manifest["throughWeek"],
        "bundleCount": len(entries),
        "teamBundles": sum(entry["family"] == "team" for entry in entries),
        "playerBundles": sum(entry["family"] == "player" for entry in entries),
        "sourceVersion": manifest["sourceVersion"],
    }


def _safe_rmtree(path: Path, *, allowed_parent: Path) -> None:
    resolved = path.resolve()
    parent = allowed_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise DepthSnapExportError(f"Refusing to remove path outside {parent}: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def staging_directory(active: Path) -> Path:
    active = Path(active).resolve()
    root = active.parent / ".staging"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{active.name}-{uuid.uuid4().hex}"


def promote_staged_registry(
    staging: Path,
    active: Path,
    *,
    keep_rollback: bool = True,
) -> Path | None:
    staging = Path(staging).resolve()
    active = Path(active).resolve()
    if staging.parent.name != ".staging" or staging.parent.parent != active.parent:
        raise DepthSnapExportError("Staging and active directories are not siblings under one data root")
    validate_registry(staging)
    rollback = active.parent / f"{active.name}.rollback"
    if rollback.exists():
        _safe_rmtree(rollback, allowed_parent=active.parent)
    moved_active = False
    try:
        if active.exists():
            os.replace(active, rollback)
            moved_active = True
        os.replace(staging, active)
    except Exception as exc:
        if moved_active and rollback.exists() and not active.exists():
            os.replace(rollback, active)
        raise DepthSnapExportError("Atomic registry promotion failed and was rolled back") from exc
    validate_registry(active)
    if moved_active and not keep_rollback:
        _safe_rmtree(rollback, allowed_parent=active.parent)
        return None
    return rollback if moved_active else None


def build_and_promote(
    spec: RegistrySpec,
    active: Path = ACTIVE_EXPORT_DIRECTORY,
    *,
    keep_rollback: bool = True,
) -> Mapping[str, Any]:
    active = Path(active).resolve()
    stage = staging_directory(active)
    try:
        write_registry(stage, spec)
        promote_staged_registry(stage, active, keep_rollback=keep_rollback)
    except Exception:
        if stage.exists():
            _safe_rmtree(stage, allowed_parent=stage.parent)
        raise
    return validate_registry(active)


def rollback_registry(active: Path = ACTIVE_EXPORT_DIRECTORY) -> Mapping[str, Any]:
    active = Path(active).resolve()
    rollback = active.parent / f"{active.name}.rollback"
    if not active.is_dir() or not rollback.is_dir():
        raise DepthSnapExportError("Both active and rollback registries are required")
    validate_registry(rollback)
    swap = active.parent / f".{active.name}.rollback-swap-{uuid.uuid4().hex}"
    try:
        os.replace(active, swap)
        os.replace(rollback, active)
        os.replace(swap, rollback)
    except Exception as exc:
        if swap.exists() and not active.exists():
            os.replace(swap, active)
        raise DepthSnapExportError("Atomic registry rollback failed") from exc
    return validate_registry(active)


def cleanup_registry_artifacts(
    active: Path = ACTIVE_EXPORT_DIRECTORY,
    *,
    remove_rollback: bool = False,
) -> Mapping[str, int]:
    active = Path(active).resolve()
    staging_root = active.parent / ".staging"
    removed_staging = 0
    if staging_root.is_dir():
        for candidate in staging_root.iterdir():
            if candidate.name.startswith(f"{active.name}-"):
                _safe_rmtree(candidate, allowed_parent=staging_root)
                removed_staging += 1
        if not any(staging_root.iterdir()):
            staging_root.rmdir()
    removed_rollback = 0
    rollback = active.parent / f"{active.name}.rollback"
    if remove_rollback and rollback.exists():
        _safe_rmtree(rollback, allowed_parent=active.parent)
        removed_rollback = 1
    return {
        "stagingDirectoriesRemoved": removed_staging,
        "rollbackDirectoriesRemoved": removed_rollback,
    }


def write_opportunity_context_preservation_report(path: Path) -> Mapping[str, Any]:
    artifacts = source_artifacts(
        [
            REPO_ROOT / "outputs" / "role_research" / "canonical_role_2025_descriptive.csv.gz",
            REPO_ROOT / "outputs" / "role_research" / "opportunity_events.csv.gz",
            REPO_ROOT / "outputs" / "role_research" / "game_player_usage.csv.gz",
            REPO_ROOT / "outputs" / "role_research" / "build_manifest.json",
        ]
    )
    payload = {
        "schemaVersion": 1,
        "season": 2025,
        "purpose": "Private exporter-side preservation inventory; not a public V1 bundle.",
        "sourceArtifacts": list(artifacts),
        **OPPORTUNITY_CONTEXT_PRESERVATION,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload))
    return payload
