from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.common import output_path, raw_path


TEAM_VARIANTS = {
    "ARI": ("ARI", "Arizona Cardinals"),
    "ARZ": ("ARI", "Arizona Cardinals"),
    "ATL": ("ATL", "Atlanta Falcons"),
    "BAL": ("BAL", "Baltimore Ravens"),
    "BUF": ("BUF", "Buffalo Bills"),
    "CAR": ("CAR", "Carolina Panthers"),
    "CHI": ("CHI", "Chicago Bears"),
    "CIN": ("CIN", "Cincinnati Bengals"),
    "CLE": ("CLE", "Cleveland Browns"),
    "DAL": ("DAL", "Dallas Cowboys"),
    "DEN": ("DEN", "Denver Broncos"),
    "DET": ("DET", "Detroit Lions"),
    "GB": ("GB", "Green Bay Packers"),
    "GNB": ("GB", "Green Bay Packers"),
    "HOU": ("HOU", "Houston Texans"),
    "IND": ("IND", "Indianapolis Colts"),
    "JAX": ("JAX", "Jacksonville Jaguars"),
    "JAC": ("JAX", "Jacksonville Jaguars"),
    "KC": ("KC", "Kansas City Chiefs"),
    "KAN": ("KC", "Kansas City Chiefs"),
    "LAC": ("LAC", "Los Angeles Chargers"),
    "LA CHARGERS": ("LAC", "Los Angeles Chargers"),
    "LAR": ("LAR", "Los Angeles Rams"),
    "LA RAMS": ("LAR", "Los Angeles Rams"),
    "LA": ("LAR", "Los Angeles Rams"),
    "LV": ("LV", "Las Vegas Raiders"),
    "LVR": ("LV", "Las Vegas Raiders"),
    "OAK": ("LV", "Las Vegas Raiders"),
    "MIA": ("MIA", "Miami Dolphins"),
    "MIN": ("MIN", "Minnesota Vikings"),
    "NE": ("NE", "New England Patriots"),
    "NEP": ("NE", "New England Patriots"),
    "NO": ("NO", "New Orleans Saints"),
    "NOR": ("NO", "New Orleans Saints"),
    "NYG": ("NYG", "New York Giants"),
    "NYJ": ("NYJ", "New York Jets"),
    "PHI": ("PHI", "Philadelphia Eagles"),
    "PIT": ("PIT", "Pittsburgh Steelers"),
    "SEA": ("SEA", "Seattle Seahawks"),
    "SF": ("SF", "San Francisco 49ers"),
    "SFO": ("SF", "San Francisco 49ers"),
    "TB": ("TB", "Tampa Bay Buccaneers"),
    "TAM": ("TB", "Tampa Bay Buccaneers"),
    "TEN": ("TEN", "Tennessee Titans"),
    "WAS": ("WAS", "Washington Commanders"),
    "WSH": ("WAS", "Washington Commanders"),
}


def normalize_player_name(name: object) -> str:
    text = "" if pd.isna(name) else str(name).lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonical_team(team: object) -> str:
    text = "" if pd.isna(team) else str(team).strip().upper()
    return TEAM_VARIANTS.get(text, (text, ""))[0]


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def _source_rosters() -> pd.DataFrame:
    path = raw_path("rosters.csv")
    df = _read(path)
    if df.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "player_id": df.get("gsis_id", ""),
            "player_name": df.get("full_name", ""),
            "team": df.get("team", ""),
            "position": df.get("position", ""),
            "season": df.get("season", pd.NA),
            "source_file": str(path),
        }
    )


def _source_weekly() -> pd.DataFrame:
    path = raw_path("weekly.csv")
    df = _read(path)
    if df.empty:
        return pd.DataFrame()
    player_id_col = "player_id" if "player_id" in df.columns else "player_gsis_id" if "player_gsis_id" in df.columns else ""
    name_col = "player_name" if "player_name" in df.columns else "full_name" if "full_name" in df.columns else ""
    team_col = "recent_team" if "recent_team" in df.columns else "team" if "team" in df.columns else ""
    return pd.DataFrame(
        {
            "player_id": df.get(player_id_col, ""),
            "player_name": df.get(name_col, ""),
            "team": df.get(team_col, ""),
            "position": df.get("position", ""),
            "season": df.get("season", pd.NA),
            "source_file": str(path),
        }
    )


def _source_projection() -> pd.DataFrame:
    path = output_path("receptions_projection_week_01_candidates.csv")
    df = _read(path)
    if df.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "player_id": df.get("player_id", ""),
            "player_name": df.get("player_name", ""),
            "team": df.get("team", ""),
            "position": df.get("position", ""),
            "season": df.get("season", pd.NA),
            "source_file": str(path),
        }
    )


def build_team_crosswalk() -> pd.DataFrame:
    rows = [
        {"raw_team": raw, "canonical_team": canonical, "team_name": name, "notes": "Built-in NFL abbreviation variant."}
        for raw, (canonical, name) in sorted(TEAM_VARIANTS.items())
    ]
    out = pd.DataFrame(rows)
    out.to_csv(output_path("identity/team_abbreviation_crosswalk.csv"), index=False)
    return out


def build_player_crosswalk() -> tuple[pd.DataFrame, pd.DataFrame]:
    sources = [_source_rosters(), _source_weekly(), _source_projection()]
    combined = pd.concat([df for df in sources if not df.empty], ignore_index=True) if any(not df.empty for df in sources) else pd.DataFrame()
    if combined.empty:
        out = pd.DataFrame(
            columns=[
                "player_id",
                "player_name",
                "normalized_player_name",
                "team",
                "position",
                "season_min",
                "season_max",
                "source_files",
                "candidate_count",
                "duplicate_name_flag",
                "notes",
            ]
        )
        dupes = pd.DataFrame(columns=["normalized_player_name", "players", "teams", "positions", "player_ids", "warning"])
        out.to_csv(output_path("identity/player_identity_crosswalk.csv"), index=False)
        dupes.to_csv(output_path("identity/duplicate_name_warnings.csv"), index=False)
        return out, dupes

    combined = combined.dropna(subset=["player_id", "player_name"], how="all").copy()
    combined["player_id"] = combined["player_id"].fillna("").astype(str).str.strip()
    combined["player_name"] = combined["player_name"].fillna("").astype(str).str.strip()
    combined["normalized_player_name"] = combined["player_name"].map(normalize_player_name)
    combined["team"] = combined["team"].map(canonical_team)
    combined["position"] = combined["position"].fillna("").astype(str).str.upper().str.strip()
    combined = combined[(combined["player_id"] != "") | (combined["normalized_player_name"] != "")]

    grouped = (
        combined.groupby(["player_id", "normalized_player_name", "team", "position"], dropna=False)
        .agg(
            player_name=("player_name", lambda s: sorted(set(x for x in s if x))[0] if any(s) else ""),
            season_min=("season", "min"),
            season_max=("season", "max"),
            source_files=("source_file", lambda s: "|".join(sorted(set(map(str, s))))),
        )
        .reset_index()
    )
    name_counts = grouped.groupby("normalized_player_name", dropna=False)["player_id"].nunique().rename("candidate_count")
    grouped = grouped.merge(name_counts, on="normalized_player_name", how="left")
    grouped["duplicate_name_flag"] = grouped["candidate_count"] > 1
    grouped["notes"] = grouped["duplicate_name_flag"].map(
        {True: "Duplicate normalized name; require player_id or team-qualified match.", False: "Identity candidate."}
    )
    out = grouped[
        [
            "player_id",
            "player_name",
            "normalized_player_name",
            "team",
            "position",
            "season_min",
            "season_max",
            "source_files",
            "candidate_count",
            "duplicate_name_flag",
            "notes",
        ]
    ].sort_values(["normalized_player_name", "team", "player_id"])

    dupes = (
        out[out["duplicate_name_flag"]]
        .groupby("normalized_player_name", as_index=False)
        .agg(
            players=("player_name", lambda s: "|".join(sorted(set(s)))),
            teams=("team", lambda s: "|".join(sorted(set(s)))),
            positions=("position", lambda s: "|".join(sorted(set(s)))),
            player_ids=("player_id", lambda s: "|".join(sorted(set(s)))),
        )
    )
    dupes["warning"] = "Duplicate normalized player name. Do not auto-match by name only."
    out.to_csv(output_path("identity/player_identity_crosswalk.csv"), index=False)
    dupes.to_csv(output_path("identity/duplicate_name_warnings.csv"), index=False)
    return out, dupes


def main() -> None:
    players, dupes = build_player_crosswalk()
    teams = build_team_crosswalk()
    print(f"player_identity_crosswalk: {len(players):,} rows")
    print(f"team_abbreviation_crosswalk: {len(teams):,} rows")
    print(f"duplicate_name_warnings: {len(dupes):,} rows")


if __name__ == "__main__":
    main()
