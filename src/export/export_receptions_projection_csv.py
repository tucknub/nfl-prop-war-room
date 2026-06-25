from __future__ import annotations

from src.common import load_config, output_path
from src.export.export_sheet_gates import assert_forward_projection_gates_ready
from src.models.receptions_model import build_week_projection, get_projection_target


def export_receptions_projection_csv() -> None:
    cfg = load_config()
    assert_forward_projection_gates_ready(cfg)
    mode, _, week = get_projection_target(cfg)
    projection_all = build_week_projection(cfg, candidates_only=False)
    projection_candidates = build_week_projection(cfg, candidates_only=True)
    projection_all.to_csv(output_path(f"receptions_projection_week_{week:02d}_all.csv", cfg), index=False)
    projection_candidates.to_csv(output_path(f"receptions_projection_week_{week:02d}_candidates.csv", cfg), index=False)
    projection_candidates.to_csv(output_path(f"receptions_projection_week_{week:02d}.csv", cfg), index=False)
    projection_all.to_csv(output_path(f"receptions_projection_{mode}_week_{week:02d}_all.csv", cfg), index=False)
    projection_candidates.to_csv(
        output_path(f"receptions_projection_{mode}_week_{week:02d}_candidates.csv", cfg),
        index=False,
    )


def main() -> None:
    export_receptions_projection_csv()
    print("Exported receptions projection CSV")


if __name__ == "__main__":
    main()
