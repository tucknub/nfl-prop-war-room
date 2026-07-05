import numpy as np,pandas as pd
from src.common import load_config,output_path
from src.features.build_completions_feature_table import build_completions_feature_table
from src.features.history_window import get_history_config
from src.models.completions_model import BUCKETS,bucket,project_completions
def main():
 cfg=load_config();_,end,_,_,_=get_history_config(cfg);p=output_path("completions_feature_table.csv",cfg);f=pd.read_csv(p,low_memory=False) if p.exists() else build_completions_feature_table(cfg);rows=[]
 for w in sorted(f[f.season==end].week.dropna().unique()):
  x=project_completions(f[(f.season==end)&(f.week==w)].copy(),cfg,{b:1. for b in BUCKETS});
  if x.empty:continue
  x["actual_completions"]=pd.to_numeric(x["completions"],errors="coerce").fillna(0);x["scoreable"]=(pd.to_numeric(x["career_attempts_entering"],errors="coerce").fillna(0)>=100)|(pd.to_numeric(x["prior_attempts"],errors="coerce").fillna(0)>=50);rows.append(x)
 raw=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame();d=raw[raw.scoreable].copy();d["calibration_bucket"]=bucket(d["projected_completions_raw"]);ms=[]
 for b in BUCKETS:
  q=d[d.calibration_bucket==b];pr=q.projected_completions_raw.sum();ac=q.actual_completions.sum();ms.append({"calibration_bucket":b,"rows":len(q),"calibration_multiplier":float(ac/pr) if pr>0 else 1.})
 m=pd.DataFrame(ms);mapping=dict(zip(m.calibration_bucket,m.calibration_multiplier));raw["calibration_bucket"]=bucket(raw.projected_completions_raw);raw["calibration_multiplier"]=raw.calibration_bucket.map(mapping).fillna(1.);raw["projected_completions_calibrated"]=raw.projected_completions_raw*raw.calibration_multiplier;d=raw[raw.scoreable];re=d.projected_completions_raw-d.actual_completions;ce=d.projected_completions_calibrated-d.actual_completions;summary=pd.DataFrame({"rows_scored":[len(d)],"raw_mae":[re.abs().mean()],"raw_rmse":[np.sqrt((re**2).mean())],"raw_bias":[re.mean()],"calibrated_mae":[ce.abs().mean()],"calibrated_rmse":[np.sqrt((ce**2).mean())],"calibrated_bias":[ce.mean()],"walk_forward_rule":["Week N uses features available through Week N-1"]});raw.to_csv(output_path("completions_backtest_rows_candidates.csv",cfg),index=False);summary.to_csv(output_path("completions_backtest_summary_candidates.csv",cfg),index=False);m.to_csv(output_path("completions_calibration_multipliers.csv",cfg),index=False);print(f"Wrote completions backtest with {len(d)} scored rows")
if __name__=="__main__":main()
