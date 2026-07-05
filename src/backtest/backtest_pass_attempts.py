from __future__ import annotations
import numpy as np,pandas as pd
from src.common import load_config,output_path
from src.features.build_pass_attempts_feature_table import build_pass_attempts_feature_table
from src.features.history_window import get_history_config
from src.models.pass_attempts_model import BUCKETS,assign_bucket,project_pass_attempts
def scoreable(df):return (pd.to_numeric(df.get("career_attempts_entering",0),errors="coerce").fillna(0)>=50)|(pd.to_numeric(df.get("prior_attempts",0),errors="coerce").fillna(0)>=30)
def build_multipliers(scored):
    df=scored[scored["scoreable"]].copy() if not scored.empty else pd.DataFrame(); rows=[]
    if not df.empty:df["calibration_bucket"]=assign_bucket(df["projected_pass_attempts_raw"])
    for b in BUCKETS:
        x=df[df["calibration_bucket"]==b] if not df.empty else pd.DataFrame(); p=x["projected_pass_attempts_raw"].sum() if not x.empty else 0.; a=x["actual_pass_attempts"].sum() if not x.empty else 0.
        rows.append({"calibration_bucket":b,"rows":len(x),"raw_projected_total":p,"actual_total":a,"calibration_multiplier":float(a/p) if p>0 else 1.})
    return pd.DataFrame(rows)
def apply_multipliers(scored,m):
    if scored.empty:return scored
    df=scored.copy(); mapping=dict(zip(m["calibration_bucket"],m["calibration_multiplier"])); df["calibration_bucket"]=assign_bucket(df["projected_pass_attempts_raw"]); df["calibration_multiplier"]=df["calibration_bucket"].map(mapping).fillna(1.); df["projected_pass_attempts_calibrated"]=df["projected_pass_attempts_raw"]*df["calibration_multiplier"]; return df
def summarize(scored):
    df=scored[scored["scoreable"]].copy() if not scored.empty else pd.DataFrame()
    if df.empty:return pd.DataFrame()
    raw=df["projected_pass_attempts_raw"]-df["actual_pass_attempts"]; cal=df["projected_pass_attempts_calibrated"]-df["actual_pass_attempts"]
    return pd.DataFrame({"rows_scored":[len(df)],"raw_mae":[raw.abs().mean()],"raw_rmse":[np.sqrt((raw**2).mean())],"raw_bias":[raw.mean()],"calibrated_mae":[cal.abs().mean()],"calibrated_rmse":[np.sqrt((cal**2).mean())],"calibrated_bias":[cal.mean()],"walk_forward_rule":["Week N uses features available through Week N-1"]})
def run_backtest(features,season):
    rows=[]; cfg=load_config(); season_df=features[features["season"]==season]
    for week in sorted(season_df["week"].dropna().unique()):
        proj=project_pass_attempts(season_df[season_df["week"]==week].copy(),cfg,{b:1. for b in BUCKETS})
        if proj.empty:continue
        proj["actual_pass_attempts"]=pd.to_numeric(proj["attempts"],errors="coerce").fillna(0); proj["scoreable"]=scoreable(proj); rows.append(proj)
    raw=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(); m=build_multipliers(raw); scored=apply_multipliers(raw,m); return scored,summarize(scored),m
def main():
    cfg=load_config(); _,history_end,_,_,_=get_history_config(cfg); path=output_path("pass_attempts_feature_table.csv",cfg); features=pd.read_csv(path,low_memory=False) if path.exists() else build_pass_attempts_feature_table(cfg); scored,summary,m=run_backtest(features,history_end); scored.to_csv(output_path("pass_attempts_backtest_rows_candidates.csv",cfg),index=False); summary.to_csv(output_path("pass_attempts_backtest_summary_candidates.csv",cfg),index=False); m.to_csv(output_path("pass_attempts_calibration_multipliers.csv",cfg),index=False); print(f"Wrote pass attempts backtest with {0 if summary.empty else int(summary['rows_scored'].iloc[0])} scored rows")
if __name__=="__main__":main()
