# Commands Run

Commands are listed in execution order for the repository-changing and validation workflow. Read-only inspection also used `rg`, `Get-ChildItem`, `Get-Content`, `Get-FileHash`, and bounded pandas/nflreadpy schema probes.

```powershell
git status --short --branch
git switch -c role-change-validation-v1

python -m pip install -r requirements-role-validation.txt

python scripts/build_role_validation_dataset.py --seasons 2018-2025 --coverage-seasons 2017-2025 --cache-dir data/raw/role_validation --output-dir outputs/role_validation --config config/role_change_validation.yaml

python -m pytest tests/test_role_validation.py -q

python scripts/run_role_validation.py --input outputs/role_validation/canonical_player_week_role.csv.gz --config config/role_change_validation.yaml --output-dir outputs/role_validation/fold_1 --fold fold_1 --mode development

python scripts/generate_role_validation_report.py
python scripts/validate_role_validation_outputs.py

python -m jupyter nbconvert --execute --to notebook --inplace notebooks/role_change_validation.ipynb
python -m nbconvert --execute --to notebook --inplace notebooks/role_change_validation.ipynb

python -m pytest tests/test_role_validation.py -q
python -m pytest -q
```

The first `python -m jupyter nbconvert ...` command failed because the user-site `jupyter-nbconvert` script was not on `PATH`; direct `python -m nbconvert ...` succeeded. Early builder/fold invocations exposed and then verified fixes for a truncated non-atomic cache, empty grid cells, repeated feature computation, repeated outcome lookup construction, and slow weekly selection/bootstrap. The final successful build and Fold 1 commands above were rerun unchanged after those fixes.
