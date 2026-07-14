from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "propwar_targeted_correctness_audit.ipynb"


def main() -> None:
    notebook = nbformat.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3", "language": "python", "name": "python3"
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3"}
    notebook["cells"] = [
        nbformat.v4.new_markdown_cell(
            "# PropWar Phase A — Targeted Correctness Audit\n\n"
            "This executed notebook reads the frozen audit artifacts, rechecks count-based formulas, "
            "and reports the acceptance gate. It does not alter public application code or production."
        ),
        nbformat.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n"
            "ROOT = Path.cwd()\n"
            "OUT = ROOT / 'outputs' / 'propwar_correctness_audit'\n"
            "final = json.loads((OUT / 'final_validation.json').read_text(encoding='utf-8'))\n"
            "calculations = pd.read_csv(OUT / 'calculation_discrepancies.csv')\n"
            "home = pd.read_csv(OUT / 'home_validation.csv')\n"
            "explorer = pd.read_csv(OUT / 'explorer_validation.csv')\n"
            "findings = pd.read_csv(OUT / 'findings.csv')\n"
            "final['baseline_commit'], final['source_hashes']"
        ),
        nbformat.v4.new_markdown_cell("## Coverage and count-based formula verification"),
        nbformat.v4.new_code_cell(
            "displayed = calculations[calculations.displayed_percentage.notna() & calculations.denominator.gt(0)].copy()\n"
            "displayed['formula_share'] = displayed.numerator / displayed.denominator\n"
            "formula_max_error = (displayed.formula_share - displayed.expected_percentage).abs().max()\n"
            "coverage = pd.Series(final['sample_coverage'], name='sample_count').to_frame()\n"
            "assert formula_max_error < 1e-12\n"
            "coverage"
        ),
        nbformat.v4.new_markdown_cell("## Window and share results"),
        nbformat.v4.new_code_cell(
            "window_summary = calculations.groupby(['audit_area', 'sample_type', 'status']).size().rename('rows').reset_index()\n"
            "assert not calculations.loc[calculations.audit_area.eq('Player'), 'status'].eq('FAIL').any()\n"
            "window_summary"
        ),
        nbformat.v4.new_markdown_cell("## Home, Explorer, links, and cross-page checks"),
        nbformat.v4.new_code_cell(
            "summary = pd.DataFrame({\n"
            "    'check': ['Home selected-week rows', 'Explorer zero-inclusive rows', 'Cross-page identical filters', 'Link/state'],\n"
            "    'failures': [home.status.eq('FAIL').sum(), explorer.status.eq('FAIL').sum(), final['results']['cross_page_failures'], final['results']['link_state_failures']],\n"
            "})\n"
            "summary"
        ),
        nbformat.v4.new_markdown_cell("## Severity and Phase A gate"),
        nbformat.v4.new_code_cell(
            "severity = findings.groupby('severity').size().rename('findings').to_frame()\n"
            "assert final['phase_status'] == 'FAILED'\n"
            "assert final['production_status'] == 'UNCHANGED'\n"
            "assert final['results']['critical_findings'] == 0\n"
            "severity"
        ),
        nbformat.v4.new_markdown_cell(
            "## Conclusion\n\n"
            "Phase A fails because unresolved High correctness issues remain. Production is unchanged. "
            "The next authorized action is to wait for the user's screen-recording review."
        ),
    ]
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    client = NotebookClient(notebook, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}})
    client.execute()
    nbformat.write(notebook, NOTEBOOK)
    print(f"EXECUTED NOTEBOOK: {NOTEBOOK}")


if __name__ == "__main__":
    main()
