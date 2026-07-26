from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.export import depthsnap_exporter as exporter


GENERATED_AT = "2026-07-26T12:00:00Z"


@pytest.fixture(scope="module")
def historical_registry(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("depthsnap-historical") / "export"
    result = exporter.write_registry(
        target,
        exporter.historical_registry_spec(GENERATED_AT),
    )
    assert result["bundleCount"] == 586
    return target


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_bytes(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_active_2026_registry_is_deterministic_and_truthfully_empty(tmp_path: Path) -> None:
    first = tmp_path / "first" / "export"
    second = tmp_path / "second" / "export"
    spec = exporter.active_registry_spec(GENERATED_AT)
    first_result = exporter.write_registry(first, spec)
    second_result = exporter.write_registry(second, spec)

    assert first_result == second_result
    assert relative_bytes(first) == relative_bytes(second)
    assert first_result == {
        "publicationStatus": "no_published_week",
        "season": 2026,
        "throughWeek": None,
        "bundleCount": 9,
        "teamBundles": 0,
        "playerBundles": 0,
        "sourceVersion": "sha256:8fd33bec1f63a940cb3f9bb6134d7edb326e748b7c1196a9b09c07e099a2cb74",
    }
    manifest = read_json(first / "manifest.json")
    assert manifest["generatedAt"] == GENERATED_AT
    assert manifest["sourceVersion"].startswith("sha256:")
    assert not any(entry["family"] in {"team", "player"} for entry in manifest["entries"])
    for path in (
        "reports/index.json",
        "reports/backfield.json",
        "reports/targets.json",
        "reports/movement.json",
        "teams/index.json",
        "players/index.json",
        "search.json",
    ):
        payload = read_json(first / path)
        for field in ("modules", "views", "teams", "players", "records"):
            if field in payload:
                assert payload[field] == []


def test_unavailable_state_requires_supplied_blocked_metadata(tmp_path: Path) -> None:
    status = (
        exporter.REPO_ROOT
        / "tests"
        / "fixtures"
        / "depthsnap_role_status_blocked_2026.json"
    )
    target = tmp_path / "export"
    spec = exporter.registry_spec_from_status(status, generated_at=GENERATED_AT)
    result = exporter.write_registry(target, spec)
    assert result["publicationStatus"] == "unavailable"
    assert result["bundleCount"] == 9
    assert read_json(target / "status.json")["checks"][-1]["status"] == "not_applicable"


def test_historical_registry_is_labeled_parity_only_and_has_all_identities(
    historical_registry: Path,
) -> None:
    result = exporter.validate_registry(historical_registry)
    assert result["publicationStatus"] == "published"
    assert result["season"] == 2025
    assert result["throughWeek"] == 18
    assert result["teamBundles"] == 32
    assert result["playerBundles"] == 545
    assert (historical_registry / "teams" / "ATL.json").is_file()
    status = read_json(historical_registry / "status.json")
    assert "temporary parity/review evidence" in status["limitations"][0]
    assert "formulaVersion" not in status
    assert "pipelineRunId" not in status


@pytest.mark.parametrize(
    ("report_path", "report_name"),
    [
        ("reports/backfield.json", "Backfield Control"),
        ("reports/targets.json", "Target Hierarchy"),
        ("reports/movement.json", "Role Movement"),
    ],
)
def test_report_membership_order_and_raw_counts_match_python_exactly(
    historical_registry: Path,
    report_path: str,
    report_name: str,
) -> None:
    bundle = read_json(historical_registry / report_path)
    window_by_view = {
        "last4": 4,
        "last8": 8,
        "last2": 2,
        "season": "Season",
    }
    for view in bundle["views"]:
        source = exporter.authoritative_report_rows(
            report_name,
            season=2025,
            through_week=18,
            window=window_by_view[view["viewId"]],
        )
        rows = view["rows"]
        assert len(rows) == len(source)
        assert [
            (row["player"]["id"], row["evidenceTeam"]["id"], row["roleFamily"])
            for row in rows
        ] == [
            (
                str(row.player_id),
                exporter.team_id(row.team),
                str(row.role_family),
            )
            for row in source.itertuples(index=False)
        ]
        for exported, source_row in zip(rows, source.to_dict("records")):
            current = (
                exported["movement"]["current"]
                if report_name == "Role Movement"
                else exported["current"]
            )
            assert current["numerator"] == int(source_row["raw_opportunities"])
            assert current["denominator"] == int(source_row["team_denominator"])
            if report_name == "Role Movement":
                previous = exported["movement"]["previous"]
                assert previous["numerator"] == int(source_row["prior_raw"])
                assert previous["denominator"] == int(source_row["prior_denom"])


def test_home_feed_and_composition_match_python_authority(
    historical_registry: Path,
) -> None:
    bundle = read_json(historical_registry / "home.json")
    cards, _ = exporter.build_weekly_role_report(2025, 17)
    exported = [bundle["leadFinding"], *bundle["findings"]]
    assert len(exported) == len(cards)
    assert [
        (
            row["kind"],
            row["player"]["id"],
            row["evidenceTeam"]["id"],
            row["roleFamily"],
        )
        for row in exported
    ] == [
        (
            exporter.FINDING_KINDS[str(row.category)],
            str(row.player_id),
            exporter.team_id(row.team),
            str(row.role_family),
        )
        for row in cards.itertuples(index=False)
    ]
    for output, source in zip(exported, cards.to_dict("records")):
        assert output["current"]["numerator"] == int(source["current_raw"])
        assert output["current"]["denominator"] == int(source["current_denominator"])
        assert output["headline"] == source["headline"]
    for family in ("backfield_control", "target_hierarchy", "role_movement"):
        report = read_json(
            historical_registry
            / "reports"
            / {
                "backfield_control": "backfield.json",
                "target_hierarchy": "targets.json",
                "role_movement": "movement.json",
            }[family]
        )
        default_rows = next(
            view["rows"] for view in report["views"] if view["viewId"] == "last4"
        )
        assert [
            row["player"]["id"]
            for row in bundle["reportLeaderboard"][family]
        ] == [row["player"]["id"] for row in default_rows[:3]]


def test_player_identity_is_team_neutral_and_historical_stints_remain_visible(
    historical_registry: Path,
) -> None:
    players = read_json(historical_registry / "players" / "index.json")["players"]
    assert all(
        set(record["player"])
        <= {"id", "name", "position", "href", "jerseyNumber", "searchAliases"}
        for record in players
    )
    cross_team = []
    for record in players:
        dossier = read_json(
            historical_registry / "players" / f"{record['player']['id']}.json"
        )
        for point in dossier["weeklyEvidence"]:
            if point["evidenceTeam"]["id"] != dossier["currentTeam"]["id"]:
                cross_team.append(
                    (
                        dossier["player"]["id"],
                        dossier["currentTeam"]["id"],
                        point["evidenceTeam"]["id"],
                    )
                )
    assert cross_team


def test_quality_dimensions_preserve_suspected_rows(
    historical_registry: Path,
) -> None:
    observed = set()
    for path in (historical_registry / "players").glob("*.json"):
        if path.name == "index.json":
            continue
        observed.update(
            point["participationQuality"]
            for point in read_json(path)["weeklyEvidence"]
        )
    assert {"complete", "suspected_statistical", "suspected_corroborated"} <= observed
    assert "reviewed_partial_game" not in observed


def test_atomic_promotion_failure_rollback_swap_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "data" / "export"
    first_spec = exporter.active_registry_spec("2026-07-26T12:00:00Z")
    exporter.write_registry(active, first_spec)
    original_source = read_json(active / "manifest.json")["sourceVersion"]

    blocked_status = (
        exporter.REPO_ROOT
        / "tests"
        / "fixtures"
        / "depthsnap_role_status_blocked_2026.json"
    )
    second_spec = exporter.registry_spec_from_status(
        blocked_status, generated_at="2026-07-26T13:00:00Z"
    )
    failed_stage = exporter.staging_directory(active)
    exporter.write_registry(failed_stage, second_spec)
    real_replace = exporter.os.replace

    def fail_stage_promotion(source: Path | str, destination: Path | str) -> None:
        if Path(source).resolve() == failed_stage.resolve():
            raise OSError("injected promotion failure")
        real_replace(source, destination)

    monkeypatch.setattr(exporter.os, "replace", fail_stage_promotion)
    with pytest.raises(exporter.DepthSnapExportError, match="rolled back"):
        exporter.promote_staged_registry(failed_stage, active)
    assert read_json(active / "manifest.json")["sourceVersion"] == original_source
    monkeypatch.setattr(exporter.os, "replace", real_replace)

    stage = exporter.staging_directory(active)
    exporter.write_registry(stage, second_spec)
    rollback = exporter.promote_staged_registry(stage, active)
    assert rollback and rollback.is_dir()
    assert exporter.validate_registry(active)["publicationStatus"] == "unavailable"
    assert exporter.rollback_registry(active)["publicationStatus"] == "no_published_week"

    stale = exporter.staging_directory(active)
    stale.mkdir()
    cleanup = exporter.cleanup_registry_artifacts(active, remove_rollback=True)
    assert cleanup["stagingDirectoriesRemoved"] >= 1
    assert cleanup["rollbackDirectoriesRemoved"] == 1


def test_opportunity_context_preservation_is_private_and_hashed(
    historical_registry: Path,
    tmp_path: Path,
) -> None:
    path = tmp_path / "opportunity-context-preservation.json"
    payload = exporter.write_opportunity_context_preservation_report(path)
    assert payload["publicExposure"] is False
    assert "yardline_100" in payload["sourceAvailableNotCommitted"]
    assert "down" in payload["sourceAvailableNotCommitted"]
    assert "ydstogo" in payload["sourceAvailableNotCommitted"]
    assert "offense_snaps" in payload["sourceAvailableNotCommitted"]
    assert all(item["sha256"] for item in payload["sourceArtifacts"])
    assert not any(
        "opportunityContext" in read_json(path)
        for path in historical_registry.rglob("*.json")
    )
