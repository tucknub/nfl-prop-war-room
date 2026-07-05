from src.common import load_config,output_path
from src.models.completions_model import build_week_projection,cols
C=["projection_mode","season","week","overall_rank","team_rank","position_rank","team","opponent_team","player_name","position","projected_completions_calibrated","projected_completions_raw","projected_pass_attempts_calibrated","projected_completion_rate","confidence_score","confidence_bucket","quality_flags","calibration_bucket","calibration_multiplier","usage_status"]
def export_google_sheet():
 cfg=load_config();d=cols(build_week_projection(cfg,True));
 for c in C:
  if c not in d.columns:d[c]=""
 d=d[C].sort_values("projected_completions_calibrated",ascending=False);d.to_csv(output_path("google_sheets_completions_historical_test.csv",cfg),index=False);return d
def main():d=export_google_sheet();print(f"Exported completions Google Sheets CSV with {len(d)} rows")
if __name__=="__main__":main()
