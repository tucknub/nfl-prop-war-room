from __future__ import annotations

import json
from pathlib import Path

import nbformat as nbf
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "role_validation" / "fold_2"
NOTEBOOK = ROOT / "notebooks" / "fold_2_untouched_2022_validation.ipynb"


def main() -> int:
    gates = pd.read_csv(OUTPUT / "release_gate_results_2022.csv")
    by_family = gates.set_index("role_family")
    summary = (
        f"RB carry: {by_family.at['rb_carry_share', 'status']} with "
        f"{int(by_family.at['rb_carry_share', 'alerts'])} alerts and "
        f"{100 * by_family.at['rb_carry_share', 'precision']:.1f}% precision. "
        f"RB opportunity: {by_family.at['rb_opportunity_share', 'status']}. "
        f"WR: {by_family.at['wr_target_share', 'status']}. "
        f"TE: {by_family.at['te_target_share', 'status']}. No family passes Fold 2."
    )
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            "# Fold 2 untouched-2022 role validation\n\n"
            "## tl;dr\n\n"
            + summary
            + " The 2022 execution was run once from the frozen candidate and was not used to tune a replacement."
        ),
        nbf.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "This notebook is the reader-facing companion to `outputs/role_validation/fold_2/FOLD_2_REPORT.md`. "
            "It loads the immutable machine-readable artifacts produced by the single 2022 execution.\n\n"
            "### Key Assumptions\n\n"
            "- Candidate SHA-256 is fixed before Fold 2.\n"
            "- Baselines reset within 2022 and end before confirmation.\n"
            "- Outcomes are the next two qualifying games after the alert.\n"
            "- Confirmed partial games are excluded; suspected cases remain primary.\n"
            "- Every comparator is equal-volume within role-family week."
        ),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n\n"
            "ROOT = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()\n"
            "OUTPUT = ROOT / 'outputs' / 'role_validation' / 'fold_2'\n"
            "assert OUTPUT.exists(), OUTPUT\n"
            "pd.set_option('display.max_columns', 30)"
        ),
        nbf.v4.new_markdown_cell("## Data\n\n### 1. Verify frozen inputs and data quality"),
        nbf.v4.new_code_cell(
            "fingerprint = json.loads((OUTPUT / 'frozen_config_fingerprint.json').read_text(encoding='utf-8'))\n"
            "audit = pd.read_csv(OUTPUT / 'data_audit_2022.csv')\n"
            "print('Candidate SHA-256:', fingerprint['config_sha256'])\n"
            "print('Matches Fold 1 report:', fingerprint['config_matches_fold1_report'])\n"
            "audit"
        ),
        nbf.v4.new_markdown_cell("## Results\n\n### 2. Inspect family/method performance and uncertainty"),
        nbf.v4.new_code_cell(
            "methods = pd.read_csv(OUTPUT / 'family_method_results_2022.csv')\n"
            "primary_methods = methods.loc[methods['partial_policy'].eq('PRIMARY_CONFIRMED_EXCLUDED')]\n"
            "primary_methods[['role_family','method','alerts','evaluable_alerts','precision','precision_ci_low','precision_ci_high','reversion_rate','median_retention']]"
        ),
        nbf.v4.new_markdown_cell("### 3. Apply locked release gates literally"),
        nbf.v4.new_code_cell(
            "gates = pd.read_csv(OUTPUT / 'release_gate_results_2022.csv')\n"
            "gates[['role_family','status','alerts','evaluable_alerts','precision','precision_improvement','reversion_rate','reversion_improvement','median_retention','failed_checks']]"
        ),
        nbf.v4.new_markdown_cell("### 4. Compare redeveloped 2021 with untouched 2022"),
        nbf.v4.new_code_cell(
            "generalization = pd.read_csv(OUTPUT / 'generalization_2021_vs_2022.csv')\n"
            "generalization[['role_family','development_2021_full_alerts','untouched_2022_full_alerts','development_2021_full_precision','untouched_2022_full_precision','delta_2022_minus_2021_full_precision','development_2021_precision_improvement','untouched_2022_precision_improvement','generalization_classification']]"
        ),
        nbf.v4.new_markdown_cell("### 5. Check direction and seasonal stability"),
        nbf.v4.new_code_cell(
            "direction = pd.read_csv(OUTPUT / 'direction_results_2022.csv')\n"
            "blocks = pd.read_csv(OUTPUT / 'season_block_results_2022.csv')\n"
            "display(direction.loc[direction['partial_policy'].eq('PRIMARY_CONFIRMED_EXCLUDED') & direction['method'].eq('full_propwar'), ['role_family','direction','alerts','evaluable_alerts','precision','reversion_rate','median_retention']])\n"
            "display(blocks.loc[blocks['partial_policy'].eq('PRIMARY_CONFIRMED_EXCLUDED') & blocks['method'].eq('full_propwar'), ['role_family','week_block','alerts','evaluable_alerts','precision','reversion_rate','median_retention']])"
        ),
        nbf.v4.new_markdown_cell("### 6. Verify partial-game sensitivity and equal volume"),
        nbf.v4.new_code_cell(
            "sensitivity = pd.read_csv(OUTPUT / 'family_comparisons_2022.csv')\n"
            "equal_volume = pd.read_csv(OUTPUT / 'equal_volume_verification_2022.csv')\n"
            "print('Equal-volume cells:', len(equal_volume))\n"
            "print('All equal volume:', bool(equal_volume['equal_volume'].all()))\n"
            "sensitivity[['partial_policy','role_family','full_alerts','full_evaluable_alerts','full_precision','precision_improvement','full_reversion_rate','full_median_retention']]"
        ),
        nbf.v4.new_markdown_cell(
            "## Takeaways\n\n"
            "- RB carry is encouraging but fails because it has 49 rather than 50 alerts; its lift interval crosses zero.\n"
            "- RB opportunity misses the locked 10-point naive-improvement gate and direction consistency.\n"
            "- WR does not support automated use; TE remains insufficient.\n"
            "- No 2022-based redevelopment occurred, and no family is validated."
        ),
    ]
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, NOTEBOOK)
    print(NOTEBOOK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
