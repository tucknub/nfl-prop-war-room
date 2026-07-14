from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "fold_4_untouched_2024_validation.ipynb"


def main() -> int:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            "# Fold 4 - untouched 2024 validation\n\n"
            "This notebook is a reader-facing audit of the single frozen Fold 4 execution. "
            "It reads the archived outputs only; it does not generate alerts, tune rules, "
            "or access 2025 results."
        ),
        nbf.v4.new_markdown_cell("## tl;dr"),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n"
            "import numpy as np\n\n"
            "ROOT = Path.cwd().resolve()\n"
            "if ROOT.name == 'notebooks': ROOT = ROOT.parent\n"
            "OUT = ROOT / 'outputs' / 'role_validation' / 'fold_4'\n"
            "run = json.loads((OUT / 'run_manifest.json').read_text())\n"
            "assert run['test_season'] == 2024 and not run['2025_results_used']\n"
            "assert run['seasons_admitted_to_feature_generation'] == [2024]\n"
            "recommendations = pd.read_csv(OUT / 'fold4_family_recommendations.csv')\n"
            "gates = pd.read_csv(OUT / 'fold4_gate_decisions.csv')\n"
            "display(gates[['role_family','fold4_candidate_status','failed_checks']], recommendations)"
        ),
        nbf.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "### Key Assumptions\n\n"
            "- The candidate and all release gates are byte-frozen.\n"
            "- Confirmed partial games are excluded and suspected partial games are included in the primary policy.\n"
            "- Comparators are equal-volume within every active-family week.\n"
            "- Pooled metrics use concatenated raw alert rows, not seasonal averages."
        ),
        nbf.v4.new_code_cell(
            "frozen = json.loads((OUT / 'frozen_execution_package_manifest.json').read_text())\n"
            "pre = json.loads((OUT / 'pre_run_manifest.json').read_text())\n"
            "assert frozen['candidate_config_sha256'] == '4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7'\n"
            "assert pre['seasons_admitted_to_alert_selection'] == [2024]\n"
            "assert pre['seasons_admitted_to_outcome_evaluation'] == [2024]\n"
            "pd.DataFrame([{\n"
            "    'execution_package_commit': frozen['execution_package_commit'],\n"
            "    'physically_opened': pre['source_seasons_physically_opened'],\n"
            "    'feature_seasons': pre['seasons_admitted_to_feature_generation'],\n"
            "    'alert_seasons': pre['seasons_admitted_to_alert_selection'],\n"
            "    'outcome_seasons': pre['seasons_admitted_to_outcome_evaluation'],\n"
            "}])"
        ),
        nbf.v4.new_markdown_cell("## Data"),
        nbf.v4.new_code_cell(
            "audit = pd.read_csv(OUT / 'data_audit_2024.csv')\n"
            "audit_checks = pd.read_csv(OUT / 'data_audit_checks_2024.csv')\n"
            "joins = pd.read_csv(OUT / 'join_coverage_2024.csv')\n"
            "assert audit.at[0, 'duplicate_key_rows'] == 0\n"
            "assert audit.at[0, 'required_null_cells'] == 0\n"
            "assert bool(audit_checks['passed'].all())\n"
            "assert bool(joins['coverage_rate'].eq(1.0).all())\n"
            "display(audit, audit_checks, joins)"
        ),
        nbf.v4.new_markdown_cell("## Results"),
        nbf.v4.new_code_cell(
            "alerts = pd.read_csv(OUT / 'fold4_alerts_2024.csv.gz', low_memory=False)\n"
            "primary = alerts.query(\"partial_policy == 'PRIMARY_CONFIRMED_EXCLUDED'\")\n"
            "rows = []\n"
            "for (family, method), group in primary.groupby(['role_family','method']):\n"
            "    evaluable = group['persistent'].notna()\n"
            "    reversion_evaluable = group['immediate_reversion'].notna()\n"
            "    rows.append({\n"
            "        'role_family': family, 'method': method, 'alerts': len(group),\n"
            "        'evaluable_alerts': int(evaluable.sum()),\n"
            "        'persistent_alerts': int(group.loc[evaluable,'persistent'].astype(float).sum()),\n"
            "        'precision': group.loc[evaluable,'persistent'].astype(float).mean(),\n"
            "        'reversion_rate': group.loc[reversion_evaluable,'immediate_reversion'].astype(float).mean(),\n"
            "        'median_retention': group.loc[evaluable,'retention'].median(),\n"
            "    })\n"
            "raw_recomputed = pd.DataFrame(rows)\n"
            "stored = pd.read_csv(OUT / 'active_family_method_results_2024.csv').query(\"partial_policy == 'PRIMARY_CONFIRMED_EXCLUDED'\")\n"
            "merged = stored.merge(raw_recomputed,on=['role_family','method'],suffixes=('_stored','_raw'),validate='one_to_one')\n"
            "for metric in ['alerts','evaluable_alerts','persistent_alerts','precision','reversion_rate','median_retention']:\n"
            "    assert np.allclose(merged[f'{metric}_stored'],merged[f'{metric}_raw'],equal_nan=True)\n"
            "display(raw_recomputed.sort_values(['role_family','method']))"
        ),
        nbf.v4.new_code_cell(
            "equal = pd.read_csv(OUT / 'equal_volume_verification_2024.csv')\n"
            "temporal = pd.read_csv(OUT / 'temporal_integrity_checks_2024.csv')\n"
            "direction = pd.read_csv(OUT / 'direction_results_2024.csv')\n"
            "sensitivity = pd.read_csv(OUT / 'partial_game_sensitivity_2024.csv')\n"
            "assert len(equal) == 108 and bool(equal['equal_volume'].all())\n"
            "assert bool(temporal['passed'].all())\n"
            "display(direction.query(\"partial_policy == 'PRIMARY_CONFIRMED_EXCLUDED'\"), sensitivity)"
        ),
        nbf.v4.new_code_cell(
            "cross = pd.read_csv(OUT / 'cross_season_family_2021_2024.csv')\n"
            "pooled_23 = pd.read_csv(OUT / 'pooled_untouched_family_2022_2023.csv')\n"
            "pooled_24 = pd.read_csv(OUT / 'pooled_untouched_family_2022_2024.csv')\n"
            "statuses = pd.read_csv(OUT / 'individual_season_gate_status_2021_2024.csv')\n"
            "assert set(cross['period']) == {'redeveloped_2021','untouched_2022','untouched_2023','untouched_2024'}\n"
            "display(cross, pooled_23, pooled_24, statuses)"
        ),
        nbf.v4.new_markdown_cell("## Takeaways"),
        nbf.v4.new_code_cell(
            "comparisons = pd.read_csv(OUT / 'active_family_comparisons_2024.csv').query(\"partial_policy == 'PRIMARY_CONFIRMED_EXCLUDED'\")\n"
            "weekly = pd.read_csv(OUT / 'weekly_stability_2024.csv').query(\"partial_policy == 'PRIMARY_CONFIRMED_EXCLUDED' and method == 'full_propwar'\")\n"
            "summary = comparisons[['role_family','full_alerts','full_evaluable_alerts','full_precision','naive_precision','precision_improvement','full_reversion_rate','reversion_improvement','full_median_retention']].merge(\n"
            "    gates[['role_family','fold4_candidate_status']], on='role_family', validate='one_to_one'\n"
            ").merge(recommendations[['role_family','recommendation']],on='role_family',how='left')\n"
            "display(summary, weekly[['role_family','weekly_median','weekly_maximum','zero_alert_weeks']])\n"
            "print('These point-gate decisions do not constitute validation. No 2025 result was used.')"
        ),
    ]
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, NOTEBOOK)
    print(NOTEBOOK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
