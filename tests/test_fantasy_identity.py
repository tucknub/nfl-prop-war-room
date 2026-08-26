from __future__ import annotations

import pandas as pd
import pytest

from src.fantasy.identity import (
    MATCHED,
    NEEDS_REVIEW,
    PRE_GSIS,
    TEAM_DEFENSE,
    UNRESOLVED,
    extract_propwar_player_ids,
    resolve_sleeper_player,
    resolve_sleeper_players,
    validate_ffverse_player_ids,
)


def _ffverse(*rows: dict, **single_row: object) -> pd.DataFrame:
    defaults = {
        "sleeper_id": None,
        "gsis_id": None,
        "yahoo_id": None,
        "name": None,
        "position": None,
        "team": None,
    }
    all_rows = list(rows)
    if single_row:
        all_rows.append(dict(single_row))
    if not all_rows:
        return pd.DataFrame(columns=list(defaults))
    return pd.DataFrame([{**defaults, **row} for row in all_rows])


def test_exact_sleeper_to_existing_gsis_reuses_production_player_id():
    frame = _ffverse(
        sleeper_id="4984",
        gsis_id="00-0034796",
        yahoo_id="30123",
        name="Josh Allen",
        position="QB",
        team="BUF",
    )

    result = resolve_sleeper_player(
        "4984",
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0034796"},
        sleeper_metadata={
            "full_name": "Josh Allen",
            "position": "QB",
            "team": "BUF",
            "yahoo_id": "30123",
        },
    )

    assert result.status == MATCHED
    assert result.propwar_entity_id == "00-0034796"
    assert result.gsis_id == "00-0034796"
    assert result.yahoo_id == "30123"
    assert "EXACT_SLEEPER_TO_GSIS_MATCH" in result.reason_codes
    assert "GSIS_ID_PRESENT_IN_PROPWAR_CROSSWALK" in result.reason_codes


def test_exact_ffverse_gsis_requires_existing_propwar_identity_before_acceptance():
    frame = _ffverse(
        sleeper_id="9999",
        gsis_id="00-0099999",
        name="New Player",
        position="WR",
        team="IND",
    )

    result = resolve_sleeper_player(
        "9999",
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0034796"},
    )

    assert result.status == NEEDS_REVIEW
    assert result.propwar_entity_id is None
    assert result.gsis_id == "00-0099999"
    assert "GSIS_ID_NOT_IN_PROPWAR_CROSSWALK" in result.reason_codes


def test_exact_sleeper_row_without_gsis_is_preserved_as_pre_gsis():
    frame = _ffverse(
        sleeper_id="rookie-1",
        gsis_id=None,
        yahoo_id="50001",
        name="Rookie Player",
        position="WR",
        team="IND",
    )

    result = resolve_sleeper_player(
        "rookie-1",
        ffverse_player_ids=frame,
        propwar_player_ids=set(),
    )

    assert result.status == PRE_GSIS
    assert result.propwar_entity_id is None
    assert result.gsis_id is None
    assert result.yahoo_id == "50001"
    assert result.reason_codes == ("EXACT_SLEEPER_ID_WITHOUT_GSIS_ID",)


def test_duplicate_sleeper_id_mapping_to_multiple_gsis_ids_never_auto_matches():
    frame = _ffverse(
        {"sleeper_id": "777", "gsis_id": "00-0000001", "name": "Player A"},
        {"sleeper_id": "777", "gsis_id": "00-0000002", "name": "Player A"},
    )

    result = resolve_sleeper_player(
        "777",
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0000001", "00-0000002"},
    )

    assert result.status == NEEDS_REVIEW
    assert result.propwar_entity_id is None
    assert result.gsis_id is None
    assert result.reason_codes == ("FFVERSE_SLEEPER_ID_MAPS_TO_MULTIPLE_GSIS_IDS",)


def test_name_is_validation_evidence_not_a_fallback_join_key():
    frame = _ffverse(
        sleeper_id="123",
        gsis_id="00-0000123",
        name="Same Name",
        position="WR",
        team="IND",
    )

    result = resolve_sleeper_player(
        "999",
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0000123"},
        sleeper_metadata={"full_name": "Same Name", "position": "WR", "team": "IND"},
    )

    assert result.status == UNRESOLVED
    assert result.propwar_entity_id is None
    assert result.reason_codes == ("NO_EXACT_FFVERSE_SLEEPER_ID",)


def test_exact_id_with_name_conflict_is_sent_to_review():
    frame = _ffverse(
        sleeper_id="123",
        gsis_id="00-0000123",
        name="Player One",
        position="WR",
        team="IND",
    )

    result = resolve_sleeper_player(
        "123",
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0000123"},
        sleeper_metadata={"full_name": "Different Person", "position": "WR", "team": "IND"},
    )

    assert result.status == NEEDS_REVIEW
    assert result.gsis_id == "00-0000123"
    assert "SLEEPER_NAME_CONFLICT" in result.reason_codes


def test_team_change_does_not_break_an_otherwise_exact_identity_match():
    frame = _ffverse(
        sleeper_id="123",
        gsis_id="00-0000123",
        name="Player One",
        position="WR",
        team="TEN",
    )

    result = resolve_sleeper_player(
        "123",
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0000123"},
        sleeper_metadata={"full_name": "Player One", "position": "WR", "team": "IND"},
    )

    assert result.status == MATCHED
    assert result.propwar_entity_id == "00-0000123"
    assert "TEAM_METADATA_DIFFERS" in result.reason_codes


def test_yahoo_id_conflict_blocks_acceptance_even_when_sleeper_and_gsis_are_exact():
    frame = _ffverse(
        sleeper_id="123",
        gsis_id="00-0000123",
        yahoo_id="456",
        name="Player One",
        position="WR",
        team="IND",
    )

    result = resolve_sleeper_player(
        "123",
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0000123"},
        sleeper_metadata={
            "full_name": "Player One",
            "position": "WR",
            "team": "IND",
            "yahoo_id": "999",
        },
    )

    assert result.status == NEEDS_REVIEW
    assert "SLEEPER_YAHOO_ID_CONFLICT" in result.reason_codes


def test_sleeper_team_defense_is_not_forced_through_player_identity_crosswalk():
    result = resolve_sleeper_player(
        "IND",
        ffverse_player_ids=_ffverse(),
        propwar_player_ids=set(),
        sleeper_metadata={
            "full_name": "Indianapolis Colts",
            "position": "DEF",
            "team": "IND",
            "fantasy_positions": ["DEF"],
        },
    )

    assert result.status == TEAM_DEFENSE
    assert result.propwar_entity_id is None
    assert result.reason_codes == ("SLEEPER_TEAM_DEFENSE",)


def test_batch_resolution_preserves_input_order_and_metadata():
    frame = _ffverse(
        {"sleeper_id": "1", "gsis_id": "00-1", "name": "One", "position": "RB", "team": "IND"},
        {"sleeper_id": "2", "gsis_id": None, "name": "Two", "position": "WR", "team": "IND"},
    )

    results = resolve_sleeper_players(
        ["2", "1"],
        ffverse_player_ids=frame,
        propwar_player_ids={"00-1"},
        sleeper_player_map={
            "1": {"full_name": "One", "position": "RB", "team": "IND"},
            "2": {"full_name": "Two", "position": "WR", "team": "IND"},
        },
    )

    assert [row.sleeper_id for row in results] == ["2", "1"]
    assert [row.status for row in results] == [PRE_GSIS, MATCHED]


def test_extract_propwar_player_ids_uses_only_nonblank_existing_ids():
    crosswalk = pd.DataFrame({"player_id": ["00-1", None, "", "00-2"]})

    assert extract_propwar_player_ids(crosswalk) == frozenset({"00-1", "00-2"})


def test_ffverse_schema_validation_fails_closed_when_required_columns_missing():
    with pytest.raises(ValueError, match="gsis_id"):
        validate_ffverse_player_ids(pd.DataFrame({"sleeper_id": ["1"]}))
