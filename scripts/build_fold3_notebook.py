from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "fold_3_untouched_2023_validation.ipynb"


def main() -> int:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3", "language": "python", "name": "python3"
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            "# Fold 3 — untouched 2023 validation\n\n"
            "Reproducible review of the single frozen Fold 3 execution. This notebook reads "
            "committed artifacts only; it does not select alerts, tune rules, or access 2024–2025 results."
        ),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n\n"
            "ROOT = Path.cwd().resolve()\n"
            "if ROOT.name == 'notebooks': ROOT = ROOT.parent\n"
            "OUT = ROOT / 'outputs' / 'role_validation' / 'fold_3'\n"
            "assert OUT.exists(), OUT\n"
            "run = json.loads((OUT / 'run_manifest.json').read_text())\n"
            "fingerprint = json.loads((OUT / 'frozen_config_fingerprint.json').read_text())\n"
            "assert run['test_season'] == 2023 and not run['post_2023_results_used']\n"
            "assert fingerprint['config_sha256'] == '4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7'\n"
            "run"
        ),
        nbf.v4.new_markdown_cell("## Data audit"),
        nbf.v4.new_code_cell(
            "audit = pd.read_csv(OUT / 'data_audit_2023.csv')\n"
            "joins = pd.read_csv(OUT / 'join_coverage_2023.csv')\n"
            "assert audit.at[0, 'duplicate_key_rows'] == 0\n"
            "assert audit.at[0, 'required_null_cells'] == 0\n"
            "assert (joins['matched_rows'] == joins['rows']).all()\n"
            "display(audit, joins)"
        ),
        nbf.v4.new_markdown_cell("## RB family results and locked statuses"),
        nbf.v4.new_code_cell(
            "comparisons = pd.read_csv(OUT / 'rb_family_comparisons_2023.csv')\n"
            "primary = comparisons.query(\"partial_policy == 'PRIMARY_CONFIRMED_EXCLUDED'\")\n"
            "gates = pd.read_csv(OUT / 'fold3_gate_decisions.csv')\n"
            "display(primary, gates)"
        ),
        nbf.v4.new_markdown_cell("## Direction and weekly stability"),
        nbf.v4.new_code_cell(
            "direction = pd.read_csv(OUT / 'cross_season_direction_2021_2023.csv')\n"
            "weekly = pd.read_csv(OUT / 'cross_season_weekly_2021_2023.csv')\n"
            "display(direction[direction.role_family.str.startswith('rb_')], "
            "weekly[weekly.role_family.str.startswith('rb_')])"
        ),
        nbf.v4.new_markdown_cell("## Partial-game sensitivity and pooled untouched evidence"),
        nbf.v4.new_code_cell(
            "sensitivity = pd.read_csv(OUT / 'partial_game_sensitivity_2023.csv')\n"
            "pooled = pd.read_csv(OUT / 'pooled_untouched_family_2022_2023.csv')\n"
            "display(sensitivity[sensitivity.role_family.str.startswith('rb_')], "
            "pooled[pooled.role_family.str.startswith('rb_')])"
        ),
        nbf.v4.new_markdown_cell("## Equal-volume and temporal validation"),
        nbf.v4.new_code_cell(
            "equal = pd.read_csv(OUT / 'equal_volume_verification_2023.csv')\n"
            "temporal = pd.read_csv(OUT / 'temporal_integrity_checks_2023.csv')\n"
            "assert bool(equal['equal_volume'].all())\n"
            "assert bool(temporal['passed'].all())\n"
            "print(f'Equal-volume cells: {len(equal)}; temporal checks: {len(temporal)}; all passed.')\n"
            "display(temporal)"
        ),
        nbf.v4.new_markdown_cell(
            "## Interpretation\n\n"
            "RB carry passes the unchanged Fold 3 point gates and is recommended to advance "
            "unchanged. RB opportunity remains shadow because the locked cross-period direction "
            "gate fails. Neither result is a validation claim; WR/TE remain retired."
        ),
    ]
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, NOTEBOOK)
    print(NOTEBOOK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
