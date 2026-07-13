from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "notebooks" / "fold_1_detector_diagnostics.ipynb"


def main() -> int:
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3"},
        "role_validation": {
            "allowed_seasons": [2018, 2019, 2020, 2021],
            "fold_2_executed": False,
            "checkpoint": "00d6085a55c60147e0ace46c847460ef5708e968",
        },
    }
    cells = []
    cells.append(
        nbf.v4.new_markdown_cell(
            "# Fold 1 detector diagnostics and redevelopment\n\n"
            "## TL;DR\n\n"
            "The original 2021 Fold 1 detector remains failed. This notebook reproduces the "
            "2018–2021 diagnostic artifacts, verifies family-week equal-volume comparisons, and "
            "reviews the candidate recommended for an untouched 2022 test. It does **not** execute "
            "Fold 2 or claim that the detector works."
        )
    )
    cells.append(
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n"
            "from IPython.display import display\n\n"
            "ROOT = Path.cwd()\n"
            "if not (ROOT / 'ROLE_CHANGE_VALIDATION_PROTOCOL.md').exists():\n"
            "    candidates = [p for p in [ROOT, *ROOT.parents] if (p / 'ROLE_CHANGE_VALIDATION_PROTOCOL.md').exists()]\n"
            "    if not candidates:\n"
            "        raise RuntimeError('Repository root not found')\n"
            "    ROOT = candidates[0]\n"
            "OUT = ROOT / 'outputs' / 'role_validation' / 'fold_1_diagnostics'\n"
            "ALLOWED = {2018, 2019, 2020, 2021}\n"
            "PRIMARY = 'PRIMARY_CONFIRMED_EXCLUDED'\n"
            "RECOMMENDED = 'fold2_candidate_v1_symmetric_deltas'\n\n"
            "def read(name):\n"
            "    frame = pd.read_csv(OUT / name, low_memory=False)\n"
            "    if 'season' in frame:\n"
            "        observed = set(pd.to_numeric(frame['season'], errors='coerce').dropna().astype(int))\n"
            "        assert observed <= ALLOWED, (name, observed)\n"
            "    return frame\n\n"
            "manifest = json.loads((OUT / 'run_manifest.json').read_text())\n"
            "assert manifest['fold_2_executed'] is False\n"
            "assert manifest['post_2021_results_used'] is False\n"
            "assert manifest['release_gates_changed'] is False\n"
            "manifest"
        )
    )
    cells.append(
        nbf.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "The checkpoint detector is diagnosed at family-alert grain and at the deduplicated "
            "player-week-team feed grain. Revised features use a same-season, disjoint baseline that "
            "ends before the confirmation window. Comparators are selected to exactly the full-detector "
            "count within family-season-week. Precision uses the locked 2,000-draw bootstrap; improvement "
            "uses a season-week cluster bootstrap.\n\n"
            "### Key Assumptions\n\n"
            "- Only 2018–2020 development data and revised 2021 evidence are loaded.\n"
            "- 2021 is no longer treated as untouched after redevelopment.\n"
            "- Suspected partial games remain in the primary analysis.\n"
            "- A confirmed partial requires explicit PBP evidence and a valid pre-next-team-game window.\n"
            "- Locked release gates are diagnostic only and are not modified."
        )
    )
    cells.append(nbf.v4.new_markdown_cell("## Data"))
    cells.append(
        nbf.v4.new_code_cell(
            "audit = read('canonical_redevelopment_audit_2018_2021.csv')\n"
            "missing = read('canonical_redevelopment_missingness_2018_2021.csv')\n"
            "partial_source = read('partial_game_source_coverage.csv')\n"
            "partial_counts = read('partial_game_status_counts.csv')\n"
            "assert audit['duplicate_key_rows'].sum() == 0\n"
            "assert missing['null_rows'].sum() == 0\n"
            "assert partial_source['trigger_timestamp_missing_team_games'].eq(0).all()\n"
            "display(audit)\n"
            "display(partial_source)\n"
            "display(partial_counts)"
        )
    )
    cells.append(nbf.v4.new_markdown_cell("## Results\n\n### Original Fold 1 volume, overlap, and repeats"))
    cells.append(
        nbf.v4.new_code_cell(
            "weekly_original = read('original_weekly_family_vs_deduplicated_volume_2021.csv')\n"
            "rb_overlap = read('original_rb_family_overlap_2021.csv')\n"
            "repeats = read('original_repeat_alerts_2021.csv')\n"
            "assert weekly_original['family_alert_rows'].sum() == 717\n"
            "assert weekly_original['deduplicated_feed_alerts'].sum() == 489\n"
            "display(weekly_original)\n"
            "display(rb_overlap)\n"
            "display(repeats)"
        )
    )
    cells.append(nbf.v4.new_markdown_cell("### Original method comparison and requested breakdowns"))
    cells.append(
        nbf.v4.new_code_cell(
            "methods = read('original_four_method_comparison_2021.csv')\n"
            "breakdowns = read('original_requested_breakdowns_2021.csv')\n"
            "display(methods[methods['grain'].eq('all_family_rows')])\n"
            "for dimension in ['role_family', 'direction', 'baseline_sample_bin', 'raw_player_opportunities',\n"
            "                  'team_opportunity_denominator', 'absolute_detected_change', 'partial_game_status']:\n"
            "    display(breakdowns[breakdowns['dimension'].eq(dimension)])"
        )
    )
    cells.append(nbf.v4.new_markdown_cell("### Safeguard ablations and false-positive reasons"))
    cells.append(
        nbf.v4.new_code_cell(
            "ablation = read('legacy_safeguard_ablation_value.csv')\n"
            "manual_path = OUT / 'original_false_positive_manual_adjudication_2021.csv'\n"
            "false_positives = pd.read_csv(manual_path, low_memory=False) if manual_path.exists() else read('original_false_positive_case_review_2021.csv')\n"
            "assert ablation.groupby(['ablation', 'ablation_mode'])['role_family'].nunique().eq(4).all()\n"
            "display(ablation[ablation['ablation_mode'].eq('operational')])\n"
            "reason_column = 'manual_primary_reason_code' if 'manual_primary_reason_code' in false_positives else 'primary_reason_code'\n"
            "display(false_positives.groupby(reason_column).size().rename('cases').sort_values(ascending=False))"
        )
    )
    cells.append(nbf.v4.new_markdown_cell("### Candidate screening and equal-volume integrity"))
    cells.append(
        nbf.v4.new_code_cell(
            "screens = read('candidate_axis_screen_equal_volume.csv')\n"
            "serious_equal = read('serious_candidate_equal_volume.csv')\n"
            "sensitivity_equal = read('recommended_candidate_partial_sensitivity_equal_volume.csv')\n"
            "assert screens['integrity_pass'].fillna(False).sum() == 53\n"
            "assert (~screens['integrity_pass'].fillna(False)).sum() == 1\n"
            "for check in [serious_equal, sensitivity_equal]:\n"
            "    assert check['equal_volume'].all()\n"
            "    assert check['observed_method_count'].eq(4).all()\n"
            "display(screens[~screens['integrity_pass'].fillna(False)])"
        )
    )
    cells.append(nbf.v4.new_markdown_cell("### Original versus revised and recommended family results"))
    cells.append(
        nbf.v4.new_code_cell(
            "original_vs_revised = read('original_vs_recommended_fold1_2021.csv')\n"
            "family = read('recommended_candidate_partial_sensitivity_comparisons.csv')\n"
            "primary = family[family['partial_policy'].eq(PRIMARY)]\n"
            "display(original_vs_revised)\n"
            "display(primary)"
        )
    )
    cells.append(nbf.v4.new_markdown_cell("### Direction, week blocks, feed volume, and sensitivities"))
    cells.append(
        nbf.v4.new_code_cell(
            "direction = read('recommended_candidate_partial_sensitivity_direction.csv')\n"
            "blocks = read('recommended_candidate_partial_sensitivity_block_comparisons.csv')\n"
            "weekly = read('recommended_candidate_partial_sensitivity_weekly_2021.csv')\n"
            "feed = read('recommended_candidate_partial_sensitivity_feed_summary_2021.csv')\n"
            "thresholds = read('recommended_candidate_persistence_threshold_sensitivity.csv')\n"
            "display(direction[direction['partial_policy'].eq(PRIMARY)])\n"
            "display(blocks[blocks['partial_policy'].eq(PRIMARY)])\n"
            "display(weekly[weekly['partial_policy'].eq(PRIMARY)])\n"
            "display(feed)\n"
            "display(thresholds)"
        )
    )
    cells.append(nbf.v4.new_markdown_cell("### Locked-gate diagnostic"))
    cells.append(
        nbf.v4.new_code_cell(
            "gates = read('recommended_candidate_locked_gate_diagnostic_2021.csv')\n"
            "assert gates['fold_2_executed'].eq(False).all()\n"
            "assert gates['release_gates_changed'].eq(False).all()\n"
            "assert gates['frozen_before_2021'].eq(False).all()\n"
            "display(gates)"
        )
    )
    cells.append(
        nbf.v4.new_markdown_cell(
            "## Takeaways\n\n"
            "- RB-family duplication explains part, but not most, of the original volume failure.\n"
            "- The original score weighting and concentration penalty have no selection effect.\n"
            "- The recommended symmetric candidate meets the combined-feed median operating target and "
            "has the strongest evidence for RB carry; RB opportunity carries a development reversion caveat.\n"
            "- WR and TE remain shadow-only because the evidence is sparse or unstable.\n"
            "- Revised 2021 is development evidence. Fold 2 remains unexecuted and is the next untouched test."
        )
    )
    nb["cells"] = cells
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, TARGET)
    print(TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
