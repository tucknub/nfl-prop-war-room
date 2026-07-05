from datetime import datetime,timezone
from math import erf,sqrt
import pandas as pd
from src.common import load_config,output_path
LINES=[149.5,174.5,199.5,224.5,249.5,274.5,299.5,324.5,349.5,374.5,399.5];METHOD="Normal approximation: mean=calibrated_projection, sd=passing_yards_backtest_calibrated_RMSE"
def sd(cfg):
 p=output_path("passing_yards_backtest_summary_candidates.csv",cfg);d=pd.read_csv(p,low_memory=False) if p.exists() else pd.DataFrame();return float(d.calibrated_rmse.iloc[0]) if not d.empty else 75.
def main():
 cfg=load_config();p=output_path("google_sheets_passing_yards_historical_test.csv",cfg);m=pd.read_csv(p,low_memory=False);e=sd(cfg);rows=[]
 for _,q in m.iterrows():
  mean=float(q.projected_passing_yards_calibrated)
  for line in LINES:
   o=min(max(1-.5*(1+erf(((line-mean)/e)/sqrt(2))),0.),1.);rows.append({"player_name":q.player_name,"player_id":q.player_id,"team":q.team,"opponent":q.opponent_team,"position":"QB","line":line,"raw_projection":q.projected_passing_yards_raw,"calibrated_projection":mean,"projection_sd":e,"model_over_probability":o,"model_under_probability":1-o,"probability_method":METHOD,"confidence_tier":q.confidence_bucket,"flags":q.quality_flags,"usage_status":"HISTORICAL TEST ONLY","notes":"Research only - no odds, edge, or betting recommendation."})
 l=pd.DataFrame(rows);t=l.sort_values(["line","model_over_probability"],ascending=[True,False]).groupby("line",group_keys=False).head(25).copy();t["rank"]=t.groupby("line").cumcount()+1;t=t[["line","rank","player_name","team","opponent","position","calibrated_projection","model_over_probability","confidence_tier","flags","usage_status","notes"]];l.to_csv(output_path("market_edges/passing_yards_line_ladder.csv",cfg),index=False);t.to_csv(output_path("market_edges/passing_yards_line_ladder_top_by_line.csv",cfg),index=False);s=pd.read_csv(output_path("passing_yards_backtest_summary_candidates.csv",cfg),low_memory=False).iloc[0];output_path("run_reports/latest_passing_yards_pipeline_report.md",cfg).write_text(f"# Passing Yards V1 Pipeline Report\n\nRun timestamp: `{datetime.now(timezone.utc).isoformat()}`\n\nFormula: `projected_pass_attempts x projected_yards_per_attempt = projected_passing_yards`\n\nCalibration/error method: `{METHOD}`\n\nCalibrated MAE/RMSE/bias: `{s.calibrated_mae:.6f}` / `{s.calibrated_rmse:.6f}` / `{s.calibrated_bias:.6f}`\n\nLine ladder rows: `{len(l)}`\n\nUsage status: `HISTORICAL TEST ONLY`\n",encoding="utf-8");print(f"passing_yards_line_ladder: {len(l)} rows");print(f"passing_yards_line_ladder_top_by_line: {len(t)} rows");print(f"passing_yards_error_sd: {e:.6f}")
if __name__=="__main__":main()
