import pandas as pd
from src.common import load_config,output_path
def main():
 cfg=load_config();p=output_path("passing_yards_backtest_rows_candidates.csv",cfg);d=pd.read_csv(p,low_memory=False).copy();score=d[d["scoreable"].astype(bool)].copy();score["absolute_error"]=(score.projected_passing_yards_calibrated-score.actual_passing_yards).abs();g=score.groupby("calibration_bucket",as_index=False).agg(rows=("actual_passing_yards","size"),avg_projected_passing_yards=("projected_passing_yards_calibrated","mean"),avg_actual_passing_yards=("actual_passing_yards","mean"),mae=("absolute_error","mean"));g["calibration_note"]="Candidate-only walk-forward calibration; historical-test only.";g.to_csv(output_path("passing_yards_calibration_report_candidates.csv",cfg),index=False);print(f"Wrote passing yards calibration report with {len(g)} rows")
if __name__=="__main__":main()
