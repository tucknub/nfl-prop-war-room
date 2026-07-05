from __future__ import annotations

import pandas as pd
from src.common import load_config,output_path
from src.features.build_pass_attempts_feature_table import build_pass_attempts_feature_table
from src.models.receptions_model import add_team_verification,get_projection_target

BUCKETS=["0-20","20-28","28-34","34-40","40+"]; BINS=[-0.01,20,28,34,40,99]
def assign_bucket(v:pd.Series)->pd.Series:return pd.cut(v,bins=BINS,labels=BUCKETS).astype(str)
def load_multipliers(cfg:dict)->dict[str,float]:
    result={b:1.0 for b in BUCKETS}; path=output_path("pass_attempts_calibration_multipliers.csv",cfg)
    if path.exists():
        for _,r in pd.read_csv(path,low_memory=False).iterrows():result[str(r["calibration_bucket"])]=float(r["calibration_multiplier"])
    return result
def project_pass_attempts(features:pd.DataFrame,config:dict|None=None,multipliers:dict[str,float]|None=None)->pd.DataFrame:
    cfg=config or load_config(); pos=features["position"].fillna("").astype(str).str.upper(); history=pd.to_numeric(features.get("career_attempts_entering",0),errors="coerce").fillna(0)>0; prior=pd.to_numeric(features.get("prior_attempts",0),errors="coerce").fillna(0)>0
    df=add_team_verification(features[pos.eq("QB")&(history|prior)].copy(),cfg)
    df["projected_team_pass_attempts"]=pd.to_numeric(df["projected_team_pass_attempts"],errors="coerce"); df["projected_qb_attempt_share"]=pd.to_numeric(df["projected_qb_attempt_share"],errors="coerce"); df=df.dropna(subset=["projected_team_pass_attempts","projected_qb_attempt_share"])
    df["projected_pass_attempts_raw"]=df["projected_team_pass_attempts"]*df["projected_qb_attempt_share"]; df["calibration_bucket"]=assign_bucket(df["projected_pass_attempts_raw"])
    df["calibration_multiplier"]=df["calibration_bucket"].map(multipliers or load_multipliers(cfg)).fillna(1.0); df["projected_pass_attempts_calibrated"]=df["projected_pass_attempts_raw"]*df["calibration_multiplier"]; df["projected_pass_attempts"]=df["projected_pass_attempts_calibrated"]
    df["is_prop_candidate"]=(df["projected_pass_attempts_calibrated"]>=10)&df["current_team_verified"].astype(bool); df["usage_status"]="HISTORICAL TEST ONLY"; return df.sort_values("projected_pass_attempts_calibrated",ascending=False)
def build_week_projection(config:dict|None=None,candidates_only:bool=True)->pd.DataFrame:
    cfg=config or load_config(); mode,season,week=get_projection_target(cfg); path=output_path("pass_attempts_feature_table.csv",cfg); features=pd.read_csv(path,low_memory=False) if path.exists() else build_pass_attempts_feature_table(cfg)
    df=project_pass_attempts(features,cfg); df=df[(df["season"]==season)&(df["week"]==week)].copy(); df=df[df["is_prop_candidate"]].copy() if candidates_only else df; df=df.sort_values("projected_pass_attempts_calibrated",ascending=False); df["overall_rank"]=range(1,len(df)+1); df["team_rank"]=df.groupby(["season","week","team"])["projected_pass_attempts_calibrated"].rank(method="first",ascending=False).astype(int); df["position_rank"]=df.groupby(["season","week","position"])["projected_pass_attempts_calibrated"].rank(method="first",ascending=False).astype(int); df["projection_mode"]=mode; return df
def output_columns(df:pd.DataFrame)->pd.DataFrame:
    cols=["projection_mode","season","week","team","opponent_team","player_id","player_name","position","projected_team_pass_attempts","projected_qb_attempt_share","projected_pass_attempts_raw","calibration_bucket","calibration_multiplier","projected_pass_attempts_calibrated","projected_pass_attempts","is_prop_candidate","overall_rank","team_rank","position_rank","confidence_score","confidence_bucket","quality_flags","usage_status","leakage_status"]; return df[[c for c in cols if c in df.columns]].copy()
def main()->None:
    cfg=load_config(); _,_,week=get_projection_target(cfg); all_rows=output_columns(build_week_projection(cfg,False)); candidates=output_columns(build_week_projection(cfg,True)); all_rows.to_csv(output_path(f"pass_attempts_projection_week_{week:02d}_all.csv",cfg),index=False); candidates.to_csv(output_path(f"pass_attempts_projection_week_{week:02d}_candidates.csv",cfg),index=False); print(f"Wrote pass attempts all projection with {len(all_rows):,} rows"); print(f"Wrote pass attempts candidates projection with {len(candidates):,} rows")
if __name__=="__main__":main()
