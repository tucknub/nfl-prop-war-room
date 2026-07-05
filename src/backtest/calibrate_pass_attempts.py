import pandas as pd
from src.common import load_config,output_path
def main():
    cfg=load_config(); path=output_path("pass_attempts_backtest_rows_candidates.csv",cfg)
    if not path.exists():
        from src.backtest.backtest_pass_attempts import main as run
        run()
    rows=pd.read_csv(path,low_memory=False) if path.exists() else pd.DataFrame()
    if rows.empty:report=pd.DataFrame()
    else:
        df=rows[rows["scoreable"]].copy(); df["abs_error"]=(df["projected_pass_attempts_calibrated"]-df["actual_pass_attempts"]).abs(); report=df.groupby(["calibration_bucket","confidence_bucket"],dropna=False).agg(rows=("player_id","size"),avg_projected_pass_attempts=("projected_pass_attempts_raw","mean"),avg_actual_pass_attempts=("actual_pass_attempts","mean"),mae=("abs_error","mean")).reset_index(); report["calibration_note"]="Candidate-only walk-forward calibration; historical-test only."
    report.to_csv(output_path("pass_attempts_calibration_report_candidates.csv",cfg),index=False); print(f"Wrote pass attempts calibration report with {len(report):,} rows")
if __name__=="__main__":main()
