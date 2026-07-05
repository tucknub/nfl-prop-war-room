import pandas as pd
from src.common import load_config,output_path
def main():
 cfg=load_config();p=output_path("completions_backtest_rows_candidates.csv",cfg)
 if not p.exists():
  from src.backtest.backtest_completions import main as run;run()
 d=pd.read_csv(p,low_memory=False);d=d[d.scoreable].copy();d["abs_error"]=(d.projected_completions_calibrated-d.actual_completions).abs();r=d.groupby(["calibration_bucket","confidence_bucket"],dropna=False).agg(rows=("player_id","size"),avg_projected_completions=("projected_completions_raw","mean"),avg_actual_completions=("actual_completions","mean"),mae=("abs_error","mean")).reset_index();r["calibration_note"]="Candidate-only walk-forward calibration; historical-test only.";r.to_csv(output_path("completions_calibration_report_candidates.csv",cfg),index=False);print(f"Wrote completions calibration report with {len(r)} rows")
if __name__=="__main__":main()
