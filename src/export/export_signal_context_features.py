from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.common import load_config, output_path, raw_path


KEY_COLUMNS = ["season", "week", "player_id", "player_name", "team", "opponent", "position"]
RECENT_WINDOWS = [3, 5, 8]


def read_csv(path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def source_columns(frame: pd.DataFrame, requested: list[str]) -> list[str]:
    return [column for column in requested if column in frame.columns]


def target_config() -> tuple[int, int, int, int]:
    cfg = load_config()["data"]
    target_season = int(cfg.get("target_season", cfg.get("projection_season", 2025)))
    target_week = int(cfg.get("target_week", cfg.get("projection_week", 1)))
    history_start = int(cfg.get("history_start_season", target_season - 2))
    history_end = int(cfg.get("history_end_season", target_season - 1))
    return target_season, target_week, history_start, history_end


def pre_target(frame: pd.DataFrame, target_season: int, target_week: int, history_start: int, history_end: int) -> pd.DataFrame:
    if frame.empty or not {"season", "week"}.issubset(frame.columns):
        return frame.iloc[0:0].copy()
    data = frame.copy()
    data["season"] = pd.to_numeric(data["season"], errors="coerce")
    data["week"] = pd.to_numeric(data["week"], errors="coerce")
    mask = (
        (data["season"] >= history_start)
        & (data["season"] <= history_end)
        & ((data["season"] < target_season) | ((data["season"] == target_season) & (data["week"] < target_week)))
    )
    return data[mask].copy()


def reliability(sample_games: object) -> str:
    numeric = pd.to_numeric(sample_games, errors="coerce")
    count = 0 if pd.isna(numeric) else int(numeric)
    if count >= 5:
        return "HIGH"
    if count >= 3:
        return "MEDIUM"
    if count >= 1:
        return "LOW"
    return "MISSING"


def trend_label(short_value: object, long_value: object) -> str:
    short = pd.to_numeric(short_value, errors="coerce")
    long = pd.to_numeric(long_value, errors="coerce")
    if pd.isna(short) or pd.isna(long) or long == 0:
        return "MISSING"
    ratio = short / long
    if ratio >= 1.15:
        return "UP"
    if ratio <= 0.85:
        return "DOWN"
    return "STABLE"


def percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series([pd.NA] * len(series), index=series.index)
    return (numeric.rank(pct=True) * 100).round(2)


def build_recent_form_features(master: pd.DataFrame, weekly: pd.DataFrame) -> pd.DataFrame:
    out = master[KEY_COLUMNS].copy()
    metric_cols = [
        "targets",
        "receptions",
        "receiving_yards",
        "carries",
        "rushing_yards",
        "attempts",
        "completions",
        "passing_yards",
    ]
    available = source_columns(weekly, ["player_id", "player_name", "team", "season", "week", *metric_cols])
    if weekly.empty or "player_id" not in weekly.columns:
        out["recent_form_reliability"] = "MISSING"
        out["recent_form_notes"] = "weekly.csv missing player_id or no pre-target rows."
        return out

    history = weekly[available].copy()
    history["player_id"] = history["player_id"].fillna("").astype(str)
    history = history.sort_values(["player_id", "season", "week"])

    rows = []
    for player_id, group in history.groupby("player_id", dropna=False):
        group = group.tail(max(RECENT_WINDOWS)).copy()
        row: dict[str, object] = {"player_id": player_id}
        sample_games = len(group)
        for window in RECENT_WINDOWS:
            recent = group.tail(window)
            prefix = f"l{window}"
            if "targets" in recent.columns:
                row[f"{prefix}_targets"] = pd.to_numeric(recent["targets"], errors="coerce").mean()
            if "receptions" in recent.columns:
                row[f"{prefix}_receptions"] = pd.to_numeric(recent["receptions"], errors="coerce").mean()
            if "receiving_yards" in recent.columns:
                row[f"{prefix}_receiving_yards"] = pd.to_numeric(recent["receiving_yards"], errors="coerce").mean()
            if "carries" in recent.columns:
                row[f"{prefix}_carries"] = pd.to_numeric(recent["carries"], errors="coerce").mean()
            if "rushing_yards" in recent.columns:
                row[f"{prefix}_rushing_yards"] = pd.to_numeric(recent["rushing_yards"], errors="coerce").mean()
            if "attempts" in recent.columns:
                row[f"{prefix}_pass_attempts"] = pd.to_numeric(recent["attempts"], errors="coerce").mean()
            if "completions" in recent.columns:
                row[f"{prefix}_completions"] = pd.to_numeric(recent["completions"], errors="coerce").mean()
            if "passing_yards" in recent.columns:
                row[f"{prefix}_passing_yards"] = pd.to_numeric(recent["passing_yards"], errors="coerce").mean()
        row["recent_receiving_sample_games"] = sample_games
        row["recent_rushing_sample_games"] = sample_games
        row["recent_passing_sample_games"] = sample_games
        row["recent_receiving_trend"] = trend_label(row.get("l3_receiving_yards"), row.get("l8_receiving_yards"))
        row["recent_rushing_trend"] = trend_label(row.get("l3_rushing_yards"), row.get("l8_rushing_yards"))
        row["recent_passing_trend"] = trend_label(row.get("l3_passing_yards"), row.get("l8_passing_yards"))
        row["recent_form_reliability"] = reliability(sample_games)
        row["recent_form_notes"] = "Pre-target weekly player stats only."
        rows.append(row)

    features = pd.DataFrame(rows)
    out = out.merge(features, on="player_id", how="left")
    out["recent_form_reliability"] = out["recent_form_reliability"].fillna("MISSING")
    out["recent_form_notes"] = out["recent_form_notes"].fillna("No pre-target player weekly history matched.")
    return out


def build_game_environment_features(master: pd.DataFrame, schedules: pd.DataFrame) -> pd.DataFrame:
    out = master[KEY_COLUMNS].copy()
    if schedules.empty or not {"season", "week", "home_team", "away_team"}.issubset(schedules.columns):
        out["game_environment_reliability"] = "MISSING"
        out["game_environment_notes"] = "schedules.csv missing required team columns."
        return out

    target_season = int(pd.to_numeric(master["season"], errors="coerce").dropna().iloc[0]) if not master.empty else 0
    target_week = int(pd.to_numeric(master["week"], errors="coerce").dropna().iloc[0]) if not master.empty else 0
    games = schedules.copy()
    games["season"] = pd.to_numeric(games["season"], errors="coerce")
    games["week"] = pd.to_numeric(games["week"], errors="coerce")
    games = games[(games["season"].eq(target_season)) & (games["week"].eq(target_week))].copy()
    rows = []
    for _, game in games.iterrows():
        for team_col, opp_col, home_flag in [("home_team", "away_team", True), ("away_team", "home_team", False)]:
            team = str(game.get(team_col, ""))
            opponent = str(game.get(opp_col, ""))
            spread = pd.to_numeric(game.get("spread_line"), errors="coerce") if "spread_line" in games.columns else pd.NA
            total = pd.to_numeric(game.get("total_line"), errors="coerce") if "total_line" in games.columns else pd.NA
            team_spread = spread if home_flag else (-spread if pd.notna(spread) else pd.NA)
            team_total = (total / 2 - team_spread / 2) if pd.notna(total) and pd.notna(team_spread) else pd.NA
            opponent_total = (total - team_total) if pd.notna(total) and pd.notna(team_total) else pd.NA
            close_game = pd.notna(team_spread) and abs(float(team_spread)) <= 3
            favorite = "FAVORITE" if pd.notna(team_spread) and team_spread < 0 else ("UNDERDOG" if pd.notna(team_spread) and team_spread > 0 else "PICKEM_OR_UNKNOWN")
            total_bucket = "NOT_AVAILABLE"
            if pd.notna(total):
                total_bucket = "HIGH" if total >= 47 else ("LOW" if total <= 41 else "MEDIUM")
            spread_bucket = "NOT_AVAILABLE"
            if pd.notna(team_spread):
                spread_bucket = "CLOSE" if abs(float(team_spread)) <= 3 else ("BLOWOUT_RISK" if abs(float(team_spread)) >= 7 else "MODERATE")
            pass_env = "NOT_AVAILABLE"
            rush_env = "NOT_AVAILABLE"
            if pd.notna(total) and pd.notna(team_spread):
                pass_env = "POSITIVE" if favorite == "UNDERDOG" or total_bucket == "HIGH" else ("NEUTRAL" if close_game else "FRAGILE")
                rush_env = "POSITIVE" if favorite == "FAVORITE" and spread_bucket != "BLOWOUT_RISK" else ("NEUTRAL" if close_game else "FRAGILE")
            score = pd.NA
            if pd.notna(total) and pd.notna(team_spread):
                score = 50 + (8 if total_bucket == "HIGH" else (-6 if total_bucket == "LOW" else 0)) + (6 if close_game else (-8 if spread_bucket == "BLOWOUT_RISK" else 0))
                score = max(20, min(85, score))
            rows.append(
                {
                    "team": team,
                    "opponent": opponent,
                    "game_id": game.get("game_id", ""),
                    "home_team": game.get("home_team", ""),
                    "away_team": game.get("away_team", ""),
                    "is_home": home_flag,
                    "spread_line": team_spread,
                    "total_line": total,
                    "team_implied_total": team_total,
                    "opponent_implied_total": opponent_total,
                    "favorite_status": favorite,
                    "spread_bucket": spread_bucket,
                    "game_total_bucket": total_bucket,
                    "pass_volume_environment": pass_env,
                    "rush_volume_environment": rush_env,
                    "game_script_score": score,
                    "game_environment_reliability": "MEDIUM" if pd.notna(total) and pd.notna(team_spread) else "MISSING",
                    "game_environment_notes": "From schedules.csv spread_line/total_line." if pd.notna(total) and pd.notna(team_spread) else "Spread/total unavailable in schedules.csv.",
                }
            )
    games_by_team = pd.DataFrame(rows)
    out = out.merge(games_by_team, on=["team", "opponent"], how="left")
    out["game_environment_reliability"] = out["game_environment_reliability"].fillna("MISSING")
    out["game_environment_notes"] = out["game_environment_notes"].fillna("No schedule game matched team/opponent.")
    return out


def _defense_position_table(history: pd.DataFrame, position_group: list[str], metrics: list[str], prefix: str) -> pd.DataFrame:
    required = ["opponent_team", "position", "season", "week", *metrics]
    available = source_columns(history, required)
    if not set(["opponent_team", "position", "season", "week"]).issubset(available):
        return pd.DataFrame()
    data = history[available].copy()
    data = data[data["position"].astype(str).isin(position_group)]
    if data.empty:
        return pd.DataFrame()
    for metric in metrics:
        if metric in data.columns:
            data[metric] = pd.to_numeric(data[metric], errors="coerce").fillna(0)
    weekly = data.groupby(["opponent_team", "position", "season", "week"], as_index=False)[source_columns(data, metrics)].sum()
    grouped = weekly.groupby(["opponent_team", "position"], as_index=False)[source_columns(weekly, metrics)].mean()
    samples = weekly.groupby(["opponent_team", "position"], as_index=False).size().rename(columns={"size": "defense_fit_sample_games"})
    grouped = grouped.merge(samples, on=["opponent_team", "position"], how="left")
    for metric in metrics:
        if metric in grouped.columns:
            league_average = pd.to_numeric(weekly[metric], errors="coerce").mean()
            weight = (grouped["defense_fit_sample_games"] / 10).clip(upper=1.0)
            adjusted = league_average + weight * (grouped[metric] - league_average)
            grouped[f"{prefix}_{metric}_adjusted"] = adjusted
    return grouped


def build_opponent_defense_fit_features(master: pd.DataFrame, weekly: pd.DataFrame) -> pd.DataFrame:
    out = master[KEY_COLUMNS].copy()
    if weekly.empty or "opponent_team" not in weekly.columns:
        out["defense_fit_reliability"] = "MISSING"
        out["defense_fit_notes"] = "weekly.csv missing opponent_team or no pre-target rows."
        return out

    rec = _defense_position_table(weekly, ["WR", "TE", "RB", "FB"], ["targets", "receptions", "receiving_yards"], "rec")
    rush = _defense_position_table(weekly, ["RB", "FB", "QB", "WR", "TE"], ["carries", "rushing_yards"], "rush")
    qb = _defense_position_table(weekly, ["QB"], ["attempts", "completions", "passing_yards"], "pass")

    if not rec.empty:
        rec = rec.rename(
            columns={
                "opponent_team": "opponent",
                "targets": "opp_allowed_targets_to_position",
                "receptions": "opp_allowed_receptions_to_position",
                "receiving_yards": "opp_allowed_rec_yards_to_position",
                "rec_receiving_yards_adjusted": "opp_allowed_rec_yards_per_game_to_position",
            }
        )
        rec["opp_receiving_fit_score"] = percentile_score(rec["opp_allowed_rec_yards_per_game_to_position"])
        out = out.merge(rec[["opponent", "position", "opp_allowed_targets_to_position", "opp_allowed_receptions_to_position", "opp_allowed_rec_yards_to_position", "opp_allowed_rec_yards_per_game_to_position", "opp_receiving_fit_score", "defense_fit_sample_games"]], on=["opponent", "position"], how="left")

    if not rush.empty:
        rush = rush.rename(
            columns={
                "opponent_team": "opponent",
                "carries": "opp_allowed_carries_to_position",
                "rushing_yards": "opp_allowed_rush_yards_to_position",
                "rush_rushing_yards_adjusted": "opp_allowed_rush_yards_per_game_to_position",
            }
        )
        rush["opp_rushing_fit_score"] = percentile_score(rush["opp_allowed_rush_yards_per_game_to_position"])
        out = out.merge(rush[["opponent", "position", "opp_allowed_carries_to_position", "opp_allowed_rush_yards_to_position", "opp_allowed_rush_yards_per_game_to_position", "opp_rushing_fit_score", "defense_fit_sample_games"]], on=["opponent", "position"], how="left", suffixes=("", "_rush"))

    if not qb.empty:
        qb = qb.rename(
            columns={
                "opponent_team": "opponent",
                "attempts": "opp_allowed_pass_attempts",
                "completions": "opp_allowed_completions",
                "passing_yards": "opp_allowed_passing_yards",
                "pass_passing_yards_adjusted": "opp_allowed_passing_yards_per_game",
            }
        )
        qb["opp_passing_fit_score"] = percentile_score(qb["opp_allowed_passing_yards_per_game"])
        out = out.merge(qb[["opponent", "position", "opp_allowed_pass_attempts", "opp_allowed_completions", "opp_allowed_passing_yards", "opp_allowed_passing_yards_per_game", "opp_passing_fit_score", "defense_fit_sample_games"]], on=["opponent", "position"], how="left", suffixes=("", "_pass"))

    sample_columns = [column for column in out.columns if column.startswith("defense_fit_sample_games")]
    if sample_columns:
        out["defense_fit_sample_games"] = out[sample_columns].max(axis=1)
        drop_cols = [column for column in sample_columns if column != "defense_fit_sample_games"]
        out = out.drop(columns=drop_cols, errors="ignore")
    else:
        out["defense_fit_sample_games"] = pd.NA

    out["defense_fit_reliability"] = out["defense_fit_sample_games"].map(reliability)
    out["opp_receiving_fit_reliability"] = out["defense_fit_reliability"].where(out["opp_receiving_fit_score"].notna(), "MISSING") if "opp_receiving_fit_score" in out.columns else "MISSING"
    out["opp_rushing_fit_reliability"] = out["defense_fit_reliability"].where(out["opp_rushing_fit_score"].notna(), "MISSING") if "opp_rushing_fit_score" in out.columns else "MISSING"
    out["opp_passing_fit_reliability"] = out["defense_fit_reliability"].where(out["opp_passing_fit_score"].notna(), "MISSING") if "opp_passing_fit_score" in out.columns else "MISSING"
    out["defense_fit_notes"] = np.where(
        pd.to_numeric(out["defense_fit_sample_games"], errors="coerce").fillna(0) < 10,
        "LOW_RELIABILITY_DEFENSE_FIT: shrinkage applied to historical allowed stats.",
        "Shrinkage applied to historical allowed stats.",
    )
    return out


def combine_context(master: pd.DataFrame, recent: pd.DataFrame, environment: pd.DataFrame, defense: pd.DataFrame) -> pd.DataFrame:
    combined = master[KEY_COLUMNS].copy()
    for frame in [recent, environment, defense]:
        columns = [column for column in frame.columns if column not in KEY_COLUMNS or column in ["season", "week", "player_id"]]
        join_keys = ["season", "week", "player_id"] if "player_id" in frame.columns else KEY_COLUMNS
        if set(join_keys).issubset(frame.columns):
            combined = combined.merge(frame[join_keys + [column for column in columns if column not in join_keys]].drop_duplicates(subset=join_keys), on=join_keys, how="left")
    reliability_cols = ["recent_form_reliability", "game_environment_reliability", "defense_fit_reliability"]
    available_count = sum(combined.get(col, pd.Series(["MISSING"] * len(combined))).astype(str).isin(["HIGH", "MEDIUM", "LOW"]) for col in reliability_cols)
    combined["context_data_quality"] = (55 + available_count * 12).clip(upper=91)
    combined["context_notes"] = "Context V1 uses pre-target weekly history, schedules.csv game lines where present, and shrinkage-adjusted defense allowed stats."
    return combined


def export_signal_context_features() -> dict[str, pd.DataFrame]:
    target_season, target_week, history_start, history_end = target_config()
    master = read_csv(output_path("signal_boards/player_week_signal_master.csv"))
    if master.empty:
        master = pd.DataFrame(columns=KEY_COLUMNS)
    for column in KEY_COLUMNS:
        if column not in master.columns:
            master[column] = pd.NA
    master = master[KEY_COLUMNS].copy()
    master["player_id"] = master["player_id"].fillna("").astype(str)

    weekly = pre_target(read_csv(raw_path("weekly.csv")), target_season, target_week, history_start, history_end)
    schedules = read_csv(raw_path("schedules.csv"))

    recent = build_recent_form_features(master, weekly)
    environment = build_game_environment_features(master, schedules)
    defense = build_opponent_defense_fit_features(master, weekly)
    combined = combine_context(master, recent, environment, defense)

    recent.to_csv(output_path("signal_boards/recent_form_features.csv"), index=False)
    environment.to_csv(output_path("signal_boards/game_environment_features.csv"), index=False)
    defense.to_csv(output_path("signal_boards/opponent_defense_fit_features.csv"), index=False)
    combined.to_csv(output_path("signal_boards/signal_context_features.csv"), index=False)

    write_report(target_season, target_week, history_start, history_end, weekly, schedules, recent, environment, defense, combined)
    return {"recent": recent, "environment": environment, "defense": defense, "combined": combined}


def write_report(target_season: int, target_week: int, history_start: int, history_end: int, weekly: pd.DataFrame, schedules: pd.DataFrame, recent: pd.DataFrame, environment: pd.DataFrame, defense: pd.DataFrame, combined: pd.DataFrame) -> None:
    weekly_columns = ", ".join(source_columns(weekly, ["player_id", "player_name", "team", "opponent_team", "position", "season", "week", "targets", "receptions", "receiving_yards", "carries", "rushing_yards", "attempts", "completions", "passing_yards"]))
    schedule_columns = ", ".join(source_columns(schedules, ["game_id", "season", "week", "home_team", "away_team", "spread_line", "total_line"]))
    text = f"""# Signal Context Features Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Target season/week: `{target_season} Week {target_week}`

Allowed history window: `{history_start}-{history_end}` and no target-week player results.

## Source Inspection

- `data/raw/weekly.csv`: `{len(weekly)}` pre-target rows used; columns used: `{weekly_columns or 'none'}`
- `data/raw/schedules.csv`: `{len(schedules)}` rows inspected; columns used: `{schedule_columns or 'none'}`
- `outputs/signal_boards/player_week_signal_master.csv`: context keys and player rows used as the safe join base.

## Outputs

- Recent form rows: `{len(recent)}`
- Game environment rows: `{len(environment)}`
- Opponent defense fit rows: `{len(defense)}`
- Combined context rows: `{len(combined)}`

## Notes

Recent form uses only pre-target weekly player stats. Game environment uses `schedules.csv` spread and total columns when present. Opponent defense fit uses historical allowed stats by opponent/position with shrinkage toward league average via `min(1.0, sample_games / 10)`.

Weather, route share, first-read share, shadow coverage, and CB matchup data remain unavailable because they are not sourced by current project files.
"""
    output_path("run_reports/latest_signal_context_features_report.md").write_text(text, encoding="utf-8")


def main() -> None:
    outputs = export_signal_context_features()
    print(f"recent_form_features: {len(outputs['recent']):,} rows")
    print(f"game_environment_features: {len(outputs['environment']):,} rows")
    print(f"opponent_defense_fit_features: {len(outputs['defense']):,} rows")
    print(f"signal_context_features: {len(outputs['combined']):,} rows")


if __name__ == "__main__":
    main()
