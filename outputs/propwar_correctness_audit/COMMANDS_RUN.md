# Commands Run — PropWar Targeted Correctness Audit

All repository commands used the working directory:

`C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration`

## Safety and branch setup

```powershell
git status --short --branch
git branch --show-current
git rev-parse HEAD
git rev-parse origin/streamlit-cloud-deploy
git rev-list -n 1 production-streamlit-cloud-pre-mobile-ux-v2
git switch -c propwar-targeted-correctness-audit-v1
git status --short
```

The baseline and production-branch commit both resolved to
`8b759f18c34708300acf5e3ef84d0e4cbbbde597`. The pre-mobile rollback tag
resolved to its previously recorded checkpoint. No production branch was
checked out, changed, merged, pushed, or deployed.

## Audit generation and inspection

```powershell
python -m py_compile scripts/run_targeted_correctness_audit.py
python scripts/run_targeted_correctness_audit.py
python scripts/build_targeted_correctness_notebook.py
```

The audit runner was re-executed after correcting audit-only composite
`game_id + play_id` counting. The final execution is the artifact-generating
run represented in `final_validation.json`.

## Browser-based live verification

The Codex in-app browser opened these exact URLs:

```text
https://propwar.streamlit.app/~/+/
https://propwar.streamlit.app/~/+/players?player=00-0038555&season=2025&family=rb_carry_share
https://propwar.streamlit.app/~/+/players?player=INVALID_PLAYER&season=2025&family=wr_target_share
https://propwar.streamlit.app/~/+/teams?team=BUF&season=2025&family=rb_carry_share
https://propwar.streamlit.app/~/+/games
https://propwar.streamlit.app/~/+/reports
https://propwar.streamlit.app/~/+/explorer
```

Read-only browser actions:

- Inspected Home player hrefs and the public navigation.
- Opened a valid and invalid player URL.
- Opened the team query URL.
- Changed Explorer team/context state, then activated `Reset filters`.
- Exercised browser Back and Forward.
- Scanned rendered text on all six public pages for prohibited analytical language.
- Read error/warning console messages.

No form submission, write action, deployment, or production mutation occurred.

## Tests and validators

```powershell
python -m pytest tests/test_targeted_correctness_audit.py -q
python -m pytest -q
python -m compileall -q dashboard scripts tests
python scripts/validate_targeted_correctness_outputs.py --section descriptive
python scripts/validate_targeted_correctness_outputs.py --section cross-page
python scripts/validate_targeted_correctness_outputs.py --section link-state
python scripts/validate_targeted_correctness_outputs.py --section explorer
python scripts/validate_targeted_correctness_outputs.py --section language
python scripts/validate_targeted_correctness_outputs.py --section all
python scripts/validate_targeted_correctness_scope.py
git diff --check
git diff --cached --check
```

The link-state and Explorer validators verify faithful detection and transparent
reason-coding of known failures; they do not reinterpret those failures as
passing product behavior.

## Commit preparation

```powershell
git add docs/propwar outputs/propwar_correctness_audit notebooks/propwar_targeted_correctness_audit.ipynb scripts/run_targeted_correctness_audit.py scripts/build_targeted_correctness_notebook.py scripts/validate_targeted_correctness_outputs.py scripts/validate_targeted_correctness_scope.py tests/test_targeted_correctness_audit.py
git diff --cached --check
git commit -m "audit PropWar public calculation correctness"
```
