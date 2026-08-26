from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral, Real
from typing import Any, Collection, Iterable, Mapping, Sequence

import pandas as pd

from src.load.build_identity_crosswalk import canonical_team, normalize_player_name


MATCHED = "MATCHED"
PRE_GSIS = "PRE_GSIS"
NEEDS_REVIEW = "NEEDS_REVIEW"
UNRESOLVED = "UNRESOLVED"
TEAM_DEFENSE = "TEAM_DEFENSE"

_REQUIRED_FFVERSE_COLUMNS = {"sleeper_id", "gsis_id"}
_DEFENSE_POSITIONS = {"DEF", "DST", "D/ST"}


@dataclass(frozen=True)
class SleeperIdentityResolution:
    """Result of resolving one Sleeper player ID without mutating identity state."""

    sleeper_id: str
    status: str
    propwar_entity_id: str | None = None
    gsis_id: str | None = None
    yahoo_id: str | None = None
    name: str | None = None
    position: str | None = None
    team: str | None = None
    reason_codes: tuple[str, ...] = ()
    ffverse_rows: int = 0

    @property
    def matched(self) -> bool:
        return self.status == MATCHED

    @property
    def requires_review(self) -> bool:
        return self.status == NEEDS_REVIEW


def _clean_id(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, Integral) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, Real) and not isinstance(value, bool):
        numeric = float(value)
        if numeric.is_integer():
            return str(int(numeric))
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "na", "n/a"}:
        return None
    return text


def _clean_text(value: Any) -> str | None:
    cleaned = _clean_id(value)
    return cleaned if cleaned else None


def _to_pandas(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if hasattr(value, "to_pandas"):
        converted = value.to_pandas()
        if isinstance(converted, pd.DataFrame):
            return converted
    return pd.DataFrame(value)


def load_ffverse_player_ids() -> pd.DataFrame:
    """Load the maintained ffverse ID crosswalk through the installed nflreadpy API."""

    try:
        import nflreadpy  # type: ignore
    except ImportError as exc:  # pragma: no cover - requirements pin this in production
        raise RuntimeError("nflreadpy is required to load the ffverse player ID crosswalk") from exc

    loader = getattr(nflreadpy, "load_ff_playerids", None)
    if loader is None:
        raise RuntimeError("Installed nflreadpy does not expose load_ff_playerids()")
    return validate_ffverse_player_ids(_to_pandas(loader()))


def validate_ffverse_player_ids(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate only the columns required for exact Sleeper-to-GSIS resolution."""

    missing = sorted(_REQUIRED_FFVERSE_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"ffverse player ID data is missing required columns: {missing}")
    return frame.copy()


def extract_propwar_player_ids(identity_crosswalk: pd.DataFrame) -> frozenset[str]:
    """Return trusted production player IDs from the existing PropWar crosswalk."""

    if "player_id" not in identity_crosswalk.columns:
        raise ValueError("PropWar identity crosswalk is missing player_id")
    return frozenset(
        cleaned
        for cleaned in (_clean_id(value) for value in identity_crosswalk["player_id"].tolist())
        if cleaned
    )


def _metadata_position(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    direct = _clean_text(metadata.get("position"))
    if direct:
        return direct.upper()
    fantasy_positions = metadata.get("fantasy_positions")
    if isinstance(fantasy_positions, Sequence) and not isinstance(fantasy_positions, (str, bytes)):
        for value in fantasy_positions:
            position = _clean_text(value)
            if position:
                return position.upper()
    return None


def _metadata_name(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    full_name = _clean_text(metadata.get("full_name"))
    if full_name:
        return full_name
    first = _clean_text(metadata.get("first_name")) or ""
    last = _clean_text(metadata.get("last_name")) or ""
    combined = f"{first} {last}".strip()
    return combined or None


def _metadata_team(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    team = _clean_text(metadata.get("team"))
    return canonical_team(team) if team else None


def _is_team_defense(metadata: Mapping[str, Any] | None) -> bool:
    if not metadata:
        return False
    direct = _metadata_position(metadata)
    if direct in _DEFENSE_POSITIONS:
        return True
    fantasy_positions = metadata.get("fantasy_positions")
    if isinstance(fantasy_positions, Sequence) and not isinstance(fantasy_positions, (str, bytes)):
        return any(str(value).strip().upper() in _DEFENSE_POSITIONS for value in fantasy_positions)
    return False


def _unique_clean_values(rows: pd.DataFrame, column: str) -> tuple[str, ...]:
    if column not in rows.columns:
        return ()
    return tuple(
        sorted(
            {
                cleaned
                for cleaned in (_clean_id(value) for value in rows[column].tolist())
                if cleaned
            }
        )
    )


def _representative_value(rows: pd.DataFrame, column: str) -> str | None:
    values = _unique_clean_values(rows, column)
    return values[0] if len(values) == 1 else None


def resolve_sleeper_player(
    sleeper_id: Any,
    *,
    ffverse_player_ids: pd.DataFrame,
    propwar_player_ids: Collection[str],
    sleeper_metadata: Mapping[str, Any] | None = None,
) -> SleeperIdentityResolution:
    """Resolve one Sleeper ID using exact maintained identifiers only.

    Names, teams, and positions are validation evidence. They can force review when
    they materially contradict an exact ID mapping, but they are never used to
    create a match when the Sleeper ID itself is absent from the ffverse crosswalk.
    """

    resolved_sleeper_id = _clean_id(sleeper_id)
    if not resolved_sleeper_id:
        raise ValueError("sleeper_id is required")

    if _is_team_defense(sleeper_metadata):
        return SleeperIdentityResolution(
            sleeper_id=resolved_sleeper_id,
            status=TEAM_DEFENSE,
            name=_metadata_name(sleeper_metadata),
            position=_metadata_position(sleeper_metadata),
            team=_metadata_team(sleeper_metadata),
            reason_codes=("SLEEPER_TEAM_DEFENSE",),
        )

    ffverse = validate_ffverse_player_ids(ffverse_player_ids)
    sleeper_values = ffverse["sleeper_id"].map(_clean_id)
    rows = ffverse.loc[sleeper_values.eq(resolved_sleeper_id)].copy()

    if rows.empty:
        return SleeperIdentityResolution(
            sleeper_id=resolved_sleeper_id,
            status=UNRESOLVED,
            name=_metadata_name(sleeper_metadata),
            position=_metadata_position(sleeper_metadata),
            team=_metadata_team(sleeper_metadata),
            reason_codes=("NO_EXACT_FFVERSE_SLEEPER_ID",),
        )

    gsis_ids = _unique_clean_values(rows, "gsis_id")
    yahoo_ids = _unique_clean_values(rows, "yahoo_id")
    ffverse_name = _representative_value(rows, "name")
    ffverse_position = _representative_value(rows, "position")
    ffverse_team_raw = _representative_value(rows, "team")
    ffverse_team = canonical_team(ffverse_team_raw) if ffverse_team_raw else None

    if len(gsis_ids) > 1:
        return SleeperIdentityResolution(
            sleeper_id=resolved_sleeper_id,
            status=NEEDS_REVIEW,
            name=ffverse_name or _metadata_name(sleeper_metadata),
            position=ffverse_position or _metadata_position(sleeper_metadata),
            team=ffverse_team or _metadata_team(sleeper_metadata),
            reason_codes=("FFVERSE_SLEEPER_ID_MAPS_TO_MULTIPLE_GSIS_IDS",),
            ffverse_rows=len(rows),
        )

    if not gsis_ids:
        return SleeperIdentityResolution(
            sleeper_id=resolved_sleeper_id,
            status=PRE_GSIS,
            yahoo_id=yahoo_ids[0] if len(yahoo_ids) == 1 else None,
            name=ffverse_name or _metadata_name(sleeper_metadata),
            position=ffverse_position or _metadata_position(sleeper_metadata),
            team=ffverse_team or _metadata_team(sleeper_metadata),
            reason_codes=("EXACT_SLEEPER_ID_WITHOUT_GSIS_ID",),
            ffverse_rows=len(rows),
        )

    gsis_id = gsis_ids[0]
    reasons: list[str] = []

    if len(yahoo_ids) > 1:
        reasons.append("FFVERSE_MULTIPLE_YAHOO_IDS")

    sleeper_yahoo_id = _clean_id(sleeper_metadata.get("yahoo_id")) if sleeper_metadata else None
    if sleeper_yahoo_id and yahoo_ids and sleeper_yahoo_id not in set(yahoo_ids):
        reasons.append("SLEEPER_YAHOO_ID_CONFLICT")

    sleeper_name = _metadata_name(sleeper_metadata)
    if sleeper_name and ffverse_name:
        if normalize_player_name(sleeper_name) != normalize_player_name(ffverse_name):
            reasons.append("SLEEPER_NAME_CONFLICT")

    sleeper_position = _metadata_position(sleeper_metadata)
    if sleeper_position and ffverse_position:
        if sleeper_position.upper() != ffverse_position.upper():
            reasons.append("SLEEPER_POSITION_CONFLICT")

    sleeper_team = _metadata_team(sleeper_metadata)
    if sleeper_team and ffverse_team and sleeper_team != ffverse_team:
        reasons.append("TEAM_METADATA_DIFFERS")

    blocking_reasons = {
        "FFVERSE_MULTIPLE_YAHOO_IDS",
        "SLEEPER_YAHOO_ID_CONFLICT",
        "SLEEPER_NAME_CONFLICT",
        "SLEEPER_POSITION_CONFLICT",
    }
    if blocking_reasons.intersection(reasons):
        return SleeperIdentityResolution(
            sleeper_id=resolved_sleeper_id,
            status=NEEDS_REVIEW,
            gsis_id=gsis_id,
            yahoo_id=yahoo_ids[0] if len(yahoo_ids) == 1 else None,
            name=ffverse_name or sleeper_name,
            position=ffverse_position or sleeper_position,
            team=ffverse_team or sleeper_team,
            reason_codes=tuple(reasons),
            ffverse_rows=len(rows),
        )

    trusted_propwar_ids = {_clean_id(value) for value in propwar_player_ids}
    trusted_propwar_ids.discard(None)
    if gsis_id not in trusted_propwar_ids:
        reasons.append("GSIS_ID_NOT_IN_PROPWAR_CROSSWALK")
        return SleeperIdentityResolution(
            sleeper_id=resolved_sleeper_id,
            status=NEEDS_REVIEW,
            gsis_id=gsis_id,
            yahoo_id=yahoo_ids[0] if len(yahoo_ids) == 1 else None,
            name=ffverse_name or sleeper_name,
            position=ffverse_position or sleeper_position,
            team=ffverse_team or sleeper_team,
            reason_codes=tuple(reasons),
            ffverse_rows=len(rows),
        )

    reasons.insert(0, "EXACT_SLEEPER_TO_GSIS_MATCH")
    reasons.append("GSIS_ID_PRESENT_IN_PROPWAR_CROSSWALK")
    return SleeperIdentityResolution(
        sleeper_id=resolved_sleeper_id,
        status=MATCHED,
        propwar_entity_id=gsis_id,
        gsis_id=gsis_id,
        yahoo_id=yahoo_ids[0] if len(yahoo_ids) == 1 else None,
        name=ffverse_name or sleeper_name,
        position=ffverse_position or sleeper_position,
        team=ffverse_team or sleeper_team,
        reason_codes=tuple(reasons),
        ffverse_rows=len(rows),
    )


def resolve_sleeper_players(
    sleeper_ids: Iterable[Any],
    *,
    ffverse_player_ids: pd.DataFrame,
    propwar_player_ids: Collection[str],
    sleeper_player_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[SleeperIdentityResolution, ...]:
    """Resolve a collection of Sleeper IDs while preserving input order."""

    player_map = sleeper_player_map or {}
    results: list[SleeperIdentityResolution] = []
    for value in sleeper_ids:
        sleeper_id = _clean_id(value)
        if not sleeper_id:
            raise ValueError("sleeper_ids cannot contain blank values")
        results.append(
            resolve_sleeper_player(
                sleeper_id,
                ffverse_player_ids=ffverse_player_ids,
                propwar_player_ids=propwar_player_ids,
                sleeper_metadata=player_map.get(sleeper_id),
            )
        )
    return tuple(results)
