from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "fold_3_independent_methodological_audit.ipynb"


def main() -> int:
    nb = nbf.v4.new_notebook()
    nb["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb["metadata"]["language_info"] = {"name": "python", "version": "3"}
    nb["cells"] = [
        nbf.v4.new_markdown_cell(
            "# Independent Fold 3 methodological audit\n\n"
            "## tl;dr\n\n"
            "The committed Fold 3 arithmetic, locked-gate decisions, pooled raw aggregation, equal-volume construction, and temporal outcome labels reconcile. "
            "RB carry legitimately passes the frozen point gates and may advance unchanged; RB opportunity must remain shadow because the pre-existing direction rule fails on 2021 decreases. "
            "This is a fragile point-gate pass—not validation. Carry's 2023 lift interval crosses zero, carry-only alerts are weak relative to alerts overlapping RB opportunity, and the source manifest overstates literal post-2023 file isolation even though no 2024–2025 values entered scoring."
        ),
        nbf.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "Audited commit: `a18c5cc3e8c9124be4781bececea0a93f7b4faf8`. Sources are the committed Fold 1/2/3 alert archives, Fold 3 enriched canonical archive, locked protocol/configuration, and independently generated audit CSVs.\n\n"
            "### Key Assumptions\n\n"
            "- Primary policy excludes confirmed partial games and retains suspected cases.\n"
            "- Precision uses only rows with a two-game persistence label; reversion uses rows with a next-game label.\n"
            "- Precision CI reproduces the locked 2,000-row bootstrap with seed 850. Lift CI reproduces the 2,000 season-week cluster bootstrap.\n"
            "- This notebook does not select alerts, tune rules, execute Fold 4, or read any 2024–2025 result rows."
        ),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import hashlib, json\n"
            "import numpy as np\n"
            "import pandas as pd\n\n"
            "ROOT = Path.cwd().resolve()\n"
            "if ROOT.name == 'notebooks': ROOT = ROOT.parent\n"
            "F3 = ROOT/'outputs'/'role_validation'/'fold_3'\n"
            "AUDIT = ROOT/'outputs'/'role_validation'/'fold_3_independent_audit'\n"
            "PRIMARY = 'PRIMARY_CONFIRMED_EXCLUDED'\n"
            "RB = ['rb_carry_share','rb_opportunity_share']\n"
            "alerts = pd.read_csv(F3/'fold3_alerts_2023.csv.gz', low_memory=False)\n"
            "canonical = pd.read_csv(F3/'canonical_role_2023_enriched.csv.gz', low_memory=False)\n"
            "primary = alerts.query('partial_policy == @PRIMARY and role_family in @RB').copy()\n"
            "assert set(alerts.season.unique()) == {2023}\n"
            "assert set(canonical.season.unique()) == {2023}\n"
            "len(alerts), len(canonical)"
        ),
        nbf.v4.new_markdown_cell("## Data\n\n### 1. Confirm grain, seasons, and archive identity"),
        nbf.v4.new_code_cell(
            "def sha256(path):\n"
            "    h=hashlib.sha256()\n"
            "    with open(path,'rb') as f:\n"
            "        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)\n"
            "    return h.hexdigest()\n\n"
            "key=['partial_policy','role_family','method','season','week','player_id','team']\n"
            "profile={\n"
            " 'alert_rows':len(alerts), 'canonical_rows':len(canonical),\n"
            " 'duplicate_alert_keys':int(alerts.duplicated(key,keep=False).sum()),\n"
            " 'alert_archive_sha256':sha256(F3/'fold3_alerts_2023.csv.gz'),\n"
            " 'config_sha256':sha256(ROOT/'config'/'role_change_fold2_candidate.yaml'),\n"
            "}\n"
            "profile"
        ),
        nbf.v4.new_markdown_cell("## Results\n\n### 2. Independently recompute headline numerators and rates"),
        nbf.v4.new_code_cell(
            "def ind(s):\n"
            "    if pd.api.types.is_bool_dtype(s): return s.astype(float)\n"
            "    return s.map({True:1.,False:0.,'True':1.,'False':0.})\n\n"
            "def summarize(g):\n"
            "    p=ind(g.persistent); r=ind(g.immediate_reversion); ev=p.notna()\n"
            "    return pd.Series({\n"
            "      'alerts':len(g),'evaluable':int(ev.sum()),'persistent':int(p.sum()),\n"
            "      'precision':p.mean(),'reversion_n':int(r.notna().sum()),\n"
            "      'reversions':int(r.sum()),'reversion':r.mean(),\n"
            "      'median_retention':pd.to_numeric(g.loc[ev,'retention']).median()})\n\n"
            "headline=(primary.groupby(['role_family','method'],sort=True).apply(summarize,include_groups=False).reset_index())\n"
            "headline"
        ),
        nbf.v4.new_markdown_cell("### 3. Verify bootstrap intervals and full-versus-naive comparisons"),
        nbf.v4.new_code_cell(
            "def rate_ci(s, iterations=2000, seed=850):\n"
            "    x=ind(s).dropna().to_numpy(); rng=np.random.default_rng(seed)\n"
            "    samples=rng.choice(x,size=(iterations,len(x)),replace=True).mean(1)\n"
            "    return np.quantile(samples,[.025,.975])\n\n"
            "ci=[]\n"
            "for (family,method),g in primary.groupby(['role_family','method']):\n"
            "    lo,hi=rate_ci(g.persistent); ci.append((family,method,lo,hi))\n"
            "ci=pd.DataFrame(ci,columns=['role_family','method','ci_low','ci_high'])\n"
            "comparison=pd.read_csv(AUDIT/'family_comparisons_recomputed_2023.csv')\n"
            "display(ci,comparison)"
        ),
        nbf.v4.new_markdown_cell("### 4. Prove pooled 2022–2023 results use raw numerators and denominators"),
        nbf.v4.new_code_cell(
            "pooled=pd.read_csv(AUDIT/'pooled_recomputed_2022_2023.csv')\n"
            "proof=pooled[['role_family','full_persistent_alerts','full_evaluable_alerts','full_precision',\n"
            " 'naive_persistent_alerts','naive_evaluable_alerts','naive_precision','precision_improvement',\n"
            " 'full_immediate_reversions','full_reversion_evaluable_alerts','full_reversion_rate','full_median_retention']]\n"
            "assert np.allclose(proof.full_persistent_alerts/proof.full_evaluable_alerts,proof.full_precision)\n"
            "assert np.allclose(proof.naive_persistent_alerts/proof.naive_evaluable_alerts,proof.naive_precision)\n"
            "proof"
        ),
        nbf.v4.new_markdown_cell("### 5. Verify every locked gate and the 2021 opportunity decrease cell"),
        nbf.v4.new_code_cell(
            "gates=pd.read_csv(AUDIT/'gate_by_gate_independent_check.csv')\n"
            "directions=pd.read_csv(AUDIT/'cross_season_direction_recomputed_2021_2023.csv')\n"
            "failing=directions.query(\"role_family == 'rb_opportunity_share' and period == 'redeveloped_2021' and direction == 'decrease'\")\n"
            "display(gates,failing)\n"
            "assert len(failing)==1 and failing.iloc[0].precision_improvement < 0"
        ),
        nbf.v4.new_markdown_cell("### 6. Inspect subgroup dependence"),
        nbf.v4.new_code_cell(
            "subgroups=pd.read_csv(AUDIT/'subgroup_metrics_2023.csv')\n"
            "overlap=pd.read_csv(AUDIT/'carry_opportunity_overlap_dependence.csv')\n"
            "concentration=pd.read_csv(AUDIT/'concentration_summary_2023.csv')\n"
            "partial=pd.read_csv(AUDIT/'partial_policy_sensitivity_recomputed_2023.csv')\n"
            "display(subgroups.query(\"role_family == 'rb_carry_share'\"),overlap,concentration,partial)"
        ),
        nbf.v4.new_markdown_cell("### 7. Verify equal volume, comparator quality, temporal order, and reconstructed outcomes"),
        nbf.v4.new_code_cell(
            "equal=pd.read_csv(AUDIT/'equal_volume_independent_check.csv')\n"
            "fairness=pd.read_csv(AUDIT/'comparator_fairness_selected_rows.csv')\n"
            "rule_compliance=pd.read_csv(AUDIT/'full_alert_rule_compliance.csv')\n"
            "replay=pd.read_csv(AUDIT/'comparator_selection_replay.csv')\n"
            "temporal=pd.read_csv(AUDIT/'temporal_integrity_independent_check.csv')\n"
            "outcomes=pd.read_csv(AUDIT/'outcome_label_reconstruction.csv')\n"
            "assert len(equal)==216 and equal.equal_volume.all()\n"
            "assert temporal.passed.all() and outcomes.matched.all()\n"
            "assert rule_compliance.all_rules_satisfied.all()\n"
            "assert replay.pool_sufficient.all() and replay.selection_matches_deterministic_top_n.all()\n"
            "assert (fairness[['data_quality_pass_rate','qualifying_game_rate','identity_resolved_rate']]==1).all().all()\n"
            "display(fairness,rule_compliance,replay.groupby(['method'])[['pool_sufficient','selection_matches_deterministic_top_n']].all(),temporal,outcomes)"
        ),
        nbf.v4.new_markdown_cell(
            "## Takeaways\n\n"
            "- `rb_carry_share`: `ADVANCE_UNCHANGED_TO_FOLD_4`. This is legitimate under the frozen point gates, but fragile and not validated.\n"
            "- `rb_opportunity_share`: `CONTINUE_UNCHANGED_SHADOW_FOLD_4`. Its stronger 2023 aggregate cannot waive the pre-existing 2021 direction failure.\n"
            "- `wr_target_share`: `REMAIN_RETIRED`.\n"
            "- `te_target_share`: `REMAIN_RETIRED`.\n\n"
            "Required caveats: carry's lift CI includes zero; carry-only 2023 alerts underperform overlapping alerts; direction strata are not themselves equal-volume; the source files span through 2025 and are scanned before 2023 filtering, although no post-2023 row reaches scoring; the runner was not itself checkpointed before execution."
        ),
    ]
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, NOTEBOOK)
    print(NOTEBOOK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
