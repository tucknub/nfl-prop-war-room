from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.build_receptions_feature_table import build_receptions_feature_table


def _divide(a: pd.Series, b: pd.Series) -> pd.Series:
    return pd.to_numeric(a, errors="coerce") / pd.to_numeric(b, errors="coerce").replace(0, np.nan)


def build_pass_attempts_feature_table(config: dict | None = None) -> pd.DataFrame:
    cfg = config or load_config(); path = output_path("receptions_feature_table.csv", cfg)
    df = (pd.read_csv(path, low_memory=False) if path.exists() else build_receptions_feature_table(cfg)).copy().sort_values(["player_id","season","week"])
    for col in ["attempts","completions","passing_yards","passing_interceptions"]:
        df[col] = pd.to_numeric(df.get(col,0),errors="coerce").fillna(0)
    player=df.groupby("player_id",group_keys=False)
    df["career_attempts_entering"]=player["attempts"].cumsum()-df["attempts"]
    df["career_qb_games_entering"]=player.cumcount()
    df["career_attempts_per_game_entering"]=_divide(df["career_attempts_entering"],df["career_qb_games_entering"])
    df["attempts_last_4"]=player["attempts"].transform(lambda s:s.shift(1).rolling(4,min_periods=1).sum())
    df["qb_games_last_4"]=player["attempts"].transform(lambda s:s.shift(1).rolling(4,min_periods=1).count())
    df["recent_attempts_per_game"]=_divide(df["attempts_last_4"],df["qb_games_last_4"])
    prior=df.groupby(["player_id","season"],as_index=False).agg(prior_attempts=("attempts","sum"),prior_qb_games=("week","size")); prior["season"]+=1
    prior["prior_attempts_per_game"]=_divide(prior["prior_attempts"],prior["prior_qb_games"])
    df=df.merge(prior[["player_id","season","prior_attempts","prior_attempts_per_game"]],on=["player_id","season"],how="left")
    qb=df[df["position"].fillna("").astype(str).str.upper().eq("QB")]
    fallback=float(qb["attempts"].sum()/max((qb["attempts"]>0).sum(),1))
    games=pd.to_numeric(df.get("current_season_games_entering",0),errors="coerce").fillna(0)
    recent=df["recent_attempts_per_game"].fillna(fallback); prior_avg=df["prior_attempts_per_game"].fillna(fallback); career=df["career_attempts_per_game_entering"].fillna(prior_avg).fillna(fallback)
    df["qb_attempt_volume_baseline"]=np.select([games>=6,games>=3],[recent*.55+prior_avg*.25+career*.20,recent*.40+prior_avg*.35+career*.25],default=prior_avg*.55+career*.30+fallback*.15)
    is_qb=df["position"].fillna("").astype(str).str.upper().eq("QB") & ((df["career_attempts_entering"]>0)|(df["prior_attempts"].fillna(0)>0))
    df["qb_attempt_volume_baseline"]=np.where(is_qb,pd.to_numeric(df["qb_attempt_volume_baseline"],errors="coerce").fillna(0).clip(lower=0),0.0)
    denom=df.groupby(["season","week","team"])["qb_attempt_volume_baseline"].transform("sum").replace(0,np.nan)
    df["projected_qb_attempt_share"]=(df["qb_attempt_volume_baseline"]/denom).fillna(0).clip(0,1)
    low=df["career_attempts_entering"].fillna(0)<50; existing=df.get("quality_flags",pd.Series("",index=df.index)).fillna("").astype(str)
    needs=is_qb&low&~existing.str.contains("LOW_QB_ATTEMPT_SAMPLE",regex=False)
    df.loc[needs,"quality_flags"]=existing.loc[needs].where(existing.loc[needs]=="",existing.loc[needs]+"|")+"LOW_QB_ATTEMPT_SAMPLE"
    df["pass_attempts_sample_flag"]=np.where(is_qb&low,"LOW_QB_ATTEMPT_SAMPLE","")
    df.to_csv(output_path("pass_attempts_feature_table.csv",cfg),index=False); print(f"Built pass attempts feature table: {len(df):,} rows"); return df


def main()->None: build_pass_attempts_feature_table()
if __name__=="__main__": main()
