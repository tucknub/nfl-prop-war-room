import pandas as pd
from src.common import load_config,output_path
from src.features.build_completions_feature_table import build_completions_feature_table
from src.models.pass_attempts_model import project_pass_attempts,get_projection_target
BUCKETS=["0-15","15-20","20-24","24-28","28+"];BINS=[-.01,15,20,24,28,99]
def bucket(v):return pd.cut(v,bins=BINS,labels=BUCKETS).astype(str)
def mult(cfg):
 d={b:1. for b in BUCKETS};p=output_path("completions_calibration_multipliers.csv",cfg)
 if p.exists():
  for _,r in pd.read_csv(p,low_memory=False).iterrows():d[str(r.calibration_bucket)]=float(r.calibration_multiplier)
 return d
def project_completions(features,config=None,multipliers=None):
 cfg=config or load_config();df=project_pass_attempts(features,cfg,{b:1. for b in ["0-20","20-28","28-34","34-40","40+"]});df["projected_completion_rate"]=pd.to_numeric(df["projected_completion_rate"],errors="coerce");df=df.dropna(subset=["projected_pass_attempts_calibrated","projected_completion_rate"]);df["projected_completions_raw"]=df["projected_pass_attempts_calibrated"]*df["projected_completion_rate"];df["calibration_bucket"]=bucket(df["projected_completions_raw"]);df["calibration_multiplier"]=df["calibration_bucket"].map(multipliers or mult(cfg)).fillna(1.);df["projected_completions_calibrated"]=df["projected_completions_raw"]*df["calibration_multiplier"];df["projected_completions"]=df["projected_completions_calibrated"];df["is_prop_candidate"]=(df["projected_completions_calibrated"]>=8)&df["current_team_verified"].astype(bool);df["usage_status"]="HISTORICAL TEST ONLY";return df
def build_week_projection(config=None,candidates_only=True):
 cfg=config or load_config();mode,season,week=get_projection_target(cfg);p=output_path("completions_feature_table.csv",cfg);f=pd.read_csv(p,low_memory=False) if p.exists() else build_completions_feature_table(cfg);df=project_completions(f,cfg);df=df[(df.season==season)&(df.week==week)].copy();df=df[df.is_prop_candidate] if candidates_only else df;df=df.sort_values("projected_completions_calibrated",ascending=False);df["overall_rank"]=range(1,len(df)+1);df["team_rank"]=df.groupby(["season","week","team"])["projected_completions_calibrated"].rank(method="first",ascending=False).astype(int);df["position_rank"]=df.groupby(["season","week","position"])["projected_completions_calibrated"].rank(method="first",ascending=False).astype(int);df["projection_mode"]=mode;return df
def cols(df):
 c=["projection_mode","season","week","team","opponent_team","player_id","player_name","position","projected_pass_attempts_calibrated","projected_completion_rate","projected_completions_raw","calibration_bucket","calibration_multiplier","projected_completions_calibrated","projected_completions","is_prop_candidate","overall_rank","team_rank","position_rank","confidence_score","confidence_bucket","quality_flags","usage_status","leakage_status"];return df[[x for x in c if x in df.columns]].copy()
def main():
 cfg=load_config();_,_,w=get_projection_target(cfg);a=cols(build_week_projection(cfg,False));c=cols(build_week_projection(cfg,True));a.to_csv(output_path(f"completions_projection_week_{w:02d}_all.csv",cfg),index=False);c.to_csv(output_path(f"completions_projection_week_{w:02d}_candidates.csv",cfg),index=False);print(f"Wrote completions all projection with {len(a):,} rows");print(f"Wrote completions candidates projection with {len(c):,} rows")
if __name__=="__main__":main()
