from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from research_data import canonical_quality_profile, repo_root
from research_ui import inject_styles, page_intro, section, table


inject_styles()
page_intro(
    "Experimental Shadow Research — Not Validated",
    "Private research artifacts, validation checkpoints, pipeline evidence, and retired experiments. This page is not part of the public role-usage workflow.",
)
st.warning(
    "RB carry share and RB opportunity share remain internal shadow research. WR and TE detector families are retired. "
    "No family completed the full validation protocol."
)

profile = canonical_quality_profile()
section("Canonical data status")
cols = st.columns(4)
cols[0].metric("Rows", f"{profile['rows']:,}")
cols[1].metric("Seasons", "2018–2024")
cols[2].metric("Duplicate keys", profile["duplicate_keys"])
cols[3].metric("Required missing cells", profile["required_missing_cells"])

tabs = st.tabs(["Fold archive", "Pipeline & audit", "Raw artifacts", "Retired research"])
with tabs[0]:
    fold_rows = []
    for season, folder in [(2022, "fold_2"), (2023, "fold_3"), (2024, "fold_4")]:
        path = repo_root() / "outputs" / "role_validation" / folder / f"family_comparisons_{season}.csv"
        if path.exists():
            frame = pd.read_csv(path)
            frame.insert(0, "season", season)
            fold_rows.append(frame)
    if fold_rows:
        table(pd.concat(fold_rows, ignore_index=True), height=520)
with tabs[1]:
    manifest_path = repo_root() / "outputs" / "role_research" / "build_manifest.json"
    st.json(json.loads(manifest_path.read_text(encoding="utf-8")))
with tabs[2]:
    artifacts = sorted((repo_root() / "outputs" / "role_validation").rglob("*.md"))
    table(pd.DataFrame({"Artifact": [str(path.relative_to(repo_root())) for path in artifacts]}), height=520)
with tabs[3]:
    st.markdown(
        "- WR target-share detector: retired from validation. Target-share facts remain available publicly.\n"
        "- TE target-share detector: retired from validation. Target-share facts remain available publicly.\n"
        "- Legacy score boards and recommendation labels are not registered in public navigation."
    )
