# PropWar Role-Change Validation Package

This is a drop-in validation package for the current NFL PropWar project.

## Intended local project

- Local path: `C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection`
- Repository: `tucknub/nfl-prop-war-room`
- Current deployment branch: `streamlit-cloud-deploy`

Do not place this work in the public dashboard first. Put it on a dedicated validation branch.

## What is included

- Locked methodology and failure policy
- Data-contract audit
- Normal-game play classifier
- Equal-volume naive baseline comparison
- Role-change candidate generation
- Persistence and reversion evaluation
- Bootstrap uncertainty
- Release-gate scoring
- Reproducible notebook
- Unit tests
- CLI runner

## What is not included

This package does not contain the user's local 2018–2025 NFL data, so the included notebook executes a clearly labeled synthetic smoke test. It does not claim real PropWar performance.

## Recommended local placement

Copy this folder into the repo root, then either:

```powershell
cd "C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection"
git checkout -b role-change-validation-v1
```

Copy these items:

```text
ROLE_CHANGE_VALIDATION_PROTOCOL.md
config/role_change_validation.yaml
src/role_validation/
scripts/run_role_validation.py
notebooks/role_change_validation.ipynb
tests/test_role_validation.py
requirements-role-validation.txt
```

## Expected canonical input

One row per player-week-role family. See the protocol and YAML for required columns.

## Run

```powershell
python -m pip install -r requirements-role-validation.txt
python -m pytest tests/test_role_validation.py -q
python scripts/run_role_validation.py `
  --input "PATH_TO_PLAYER_WEEK_ROLE_TABLE.csv" `
  --config "config/role_change_validation.yaml" `
  --output-dir "outputs/role_validation"
```

## Freeze rules before the 2025 holdout

Do not manually change `rules_frozen_for_2025` without generating a fingerprint:

```powershell
python scripts/freeze_role_rules.py `
  --config "config/role_change_validation.yaml" `
  --output "config/frozen_role_rules_2025.yaml"
```

The holdout runner refuses to run a 2025 final judgment unless the frozen file contains a matching SHA-256 fingerprint.

## First real task

Run the data audit against 2018–2020, document why 2018 is the first trustworthy season, and execute Fold 1 on 2021.
