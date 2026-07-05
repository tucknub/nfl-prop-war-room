import pandas as pd
from src.common import load_config,output_path
from src.models.pass_attempts_model import build_week_projection,output_columns
COLS=["projection_mode","season","week","overall_rank","team_rank","position_rank","team","opponent_team","player_name","position","projected_pass_attempts_calibrated","projected_pass_attempts_raw","projected_team_pass_attempts","projected_qb_attempt_share","confidence_score","confidence_bucket","quality_flags","calibration_bucket","calibration_multiplier","usage_status"]
def export_google_sheet():
    cfg=load_config(); df=output_columns(build_week_projection(cfg,True))
    for c in COLS:
        if c not in df.columns:df[c]=""
    out=df[COLS].sort_values("projected_pass_attempts_calibrated",ascending=False); out.to_csv(output_path("google_sheets_pass_attempts_historical_test.csv",cfg),index=False); return out
def main():out=export_google_sheet();print(f"Exported pass attempts Google Sheets CSV with {len(out):,} rows")
if __name__=="__main__":main()
