from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from src.common import output_path


PACK_DIR = "google_sheets"
MANIFEST_NAME = "import_manifest.csv"
INSTRUCTIONS_NAME = "IMPORT_INSTRUCTIONS.md"
ZIP_NAME = "latest_import_pack.zip"


IMPORT_ITEMS = [
    {
        "file_name": "schedule_gate_import.csv",
        "google_sheet_tab": "Schedule Gate",
        "start_cell": "A13",
        "import_method": "File -> Import -> Replace data at selected cell",
        "required_for_projection": "Yes",
        "required_for_betting": "Yes",
        "notes": "Target schedule rows. If missing, gate remains NEEDS DATA. Do not fabricate schedule data.",
    },
    {
        "file_name": "roster_gate_import_template.csv",
        "google_sheet_tab": "Roster Gate",
        "start_cell": "A13",
        "import_method": "File -> Import -> Replace data at selected cell",
        "required_for_projection": "Yes",
        "required_for_betting": "Yes",
        "notes": "Current team verification template. TEAM_VERIFY means DO NOT USE.",
    },
    {
        "file_name": "role_gate_import_template.csv",
        "google_sheet_tab": "Role Gate",
        "start_cell": "A13",
        "import_method": "File -> Import -> Replace data at selected cell",
        "required_for_projection": "Yes",
        "required_for_betting": "Yes",
        "notes": "Role confidence and route/snap context. Unknown role blocks high-confidence live use.",
    },
    {
        "file_name": "injury_gate_import_template.csv",
        "google_sheet_tab": "Injury Gate",
        "start_cell": "A13",
        "import_method": "File -> Import -> Replace data at selected cell",
        "required_for_projection": "Yes",
        "required_for_betting": "Yes",
        "notes": "Availability gate. Unknown, Out, IR, Doubtful, or Inactive blocks or downgrades live use.",
    },
    {
        "file_name": "market_odds_gate_import_template.csv",
        "google_sheet_tab": "Market Odds Gate",
        "start_cell": "A14",
        "import_method": "File -> Import -> Replace data at selected cell",
        "required_for_projection": "No",
        "required_for_betting": "Yes",
        "notes": "Receptions odds template. No odds means no betting edge should be produced.",
    },
    {
        "file_name": "live_readiness_export.csv",
        "google_sheet_tab": "Live Readiness",
        "start_cell": "optional review import / do not overwrite formulas unless instructed",
        "import_method": "Review only, or import to a scratch area unless intentionally refreshing formulas",
        "required_for_projection": "Review",
        "required_for_betting": "Review",
        "notes": "Machine-readable gate summary. Avoid overwriting formula sections unless you intend to refresh them.",
    },
    {
        "file_name": "forward_projection_blockers.csv",
        "google_sheet_tab": "Forward Readiness or separate blockers review tab",
        "start_cell": "A1",
        "import_method": "File -> Import -> Replace data at selected cell",
        "required_for_projection": "Review",
        "required_for_betting": "Review",
        "notes": "Current blockers preventing forward projection and betting use.",
    },
    {
        "file_name": "../google_sheets_receptions_historical_test.csv",
        "google_sheet_tab": "Receptions Model Test",
        "start_cell": "A1",
        "import_method": "File -> Import -> Replace data at selected cell",
        "required_for_projection": "No",
        "required_for_betting": "No",
        "notes": "Historical-test model board only. Not live betting output.",
    },
    {
        "file_name": "../market_edges/receptions_line_ladder.csv",
        "manifest_file_path": "outputs/market_edges/receptions_line_ladder.csv",
        "google_sheet_tab": "Line Ladder",
        "start_cell": "A1",
        "import_method": "replace data at selected cell",
        "required_for_projection": "false",
        "required_for_betting": "false",
        "notes": "Optional research import",
    },
    {
        "file_name": "../market_edges/receptions_line_ladder_top_by_line.csv",
        "manifest_file_path": "outputs/market_edges/receptions_line_ladder_top_by_line.csv",
        "google_sheet_tab": "Line Ladder Top",
        "start_cell": "A1",
        "import_method": "replace data at selected cell",
        "required_for_projection": "false",
        "required_for_betting": "false",
        "notes": "Optional top-by-line research import",
    },
]


def _pack_path(name: str) -> Path:
    return output_path(f"{PACK_DIR}/{name}")


def _source_path(file_name: str) -> Path:
    if file_name.startswith("../"):
        return output_path(file_name[3:])
    return _pack_path(file_name)


def _read_statuses() -> tuple[dict[str, str], str, list[str], bool]:
    readiness_path = _pack_path("live_readiness_export.csv")
    blockers_path = _pack_path("forward_projection_blockers.csv")
    readiness = pd.read_csv(readiness_path, low_memory=False) if readiness_path.exists() else pd.DataFrame()
    blockers = pd.read_csv(blockers_path, low_memory=False) if blockers_path.exists() else pd.DataFrame()
    status_by_gate = dict(zip(readiness.get("Gate", []), readiness.get("Status", [])))
    final = status_by_gate.get("Final Betting Use", "UNKNOWN")
    blocked = blockers["Blocker"].dropna().astype(str).tolist() if "Blocker" in blockers.columns else []
    dashboard_path = output_path("google_sheets_receptions_historical_test.csv")
    live_betting_output_exists = False
    if dashboard_path.exists():
        dashboard = pd.read_csv(dashboard_path, low_memory=False)
        live_betting_output_exists = not dashboard.get("usage_status", pd.Series(dtype=str)).astype(str).str.contains(
            "HISTORICAL TEST ONLY|DO NOT USE",
            regex=True,
        ).all()
    return status_by_gate, final, blocked, live_betting_output_exists


def build_manifest() -> pd.DataFrame:
    status_by_gate, _, _, _ = _read_statuses()
    rows = []
    tab_to_gate = {
        "Schedule Gate": "Schedule Gate",
        "Roster Gate": "Roster Gate",
        "Role Gate": "Role Gate",
        "Injury Gate": "Injury Gate",
        "Market Odds Gate": "Market Odds Gate",
        "Live Readiness": "Final Betting Use",
        "Forward Readiness or separate blockers review tab": "Final Betting Use",
        "Receptions Model Test": "Receptions Dashboard",
        "Line Ladder": "Receptions Dashboard",
        "Line Ladder Top": "Receptions Dashboard",
    }
    for item in IMPORT_ITEMS:
        source = _source_path(item["file_name"])
        gate = tab_to_gate[item["google_sheet_tab"]]
        rows.append(
            {
                "file_path": item.get("manifest_file_path", str(source)),
                "google_sheet_tab": item["google_sheet_tab"],
                "start_cell": item["start_cell"],
                "import_method": item["import_method"],
                "required_for_projection": item["required_for_projection"],
                "required_for_betting": item["required_for_betting"],
                "current_status": status_by_gate.get(gate, "UNKNOWN"),
                "notes": item["notes"],
            }
        )
    return pd.DataFrame(rows)


def build_instructions(manifest: pd.DataFrame, final_status: str, blocked_gates: list[str]) -> str:
    lines = [
        "# Google Sheets Import Pack",
        "",
        "This pack is a local CSV import bundle. It does not upload anything to Google Sheets and does not use Google API credentials.",
        "",
        "## Current Readiness",
        "",
        f"- Final Live Readiness: `{final_status}`",
        f"- Blocked gates: `{', '.join(blocked_gates) if blocked_gates else 'None'}`",
        "- Current model mode: `historical_test` unless changed in `config.yaml`.",
        "",
        "The board is not live-betting ready until `Live Readiness = GO`.",
        "",
        "## Import Map",
        "",
        "| File | Google Sheet tab | Select cell | Import method |",
        "| --- | --- | --- | --- |",
    ]
    for _, row in manifest.iterrows():
        lines.append(
            f"| `{Path(row['file_path']).name}` | {row['google_sheet_tab']} | {row['start_cell']} | {row['import_method']} |"
        )
    lines.extend(
        [
            "",
            "## How To Import",
            "",
            "1. Open the Google Sheet control room.",
            "2. Go to the target tab listed in `import_manifest.csv`.",
            "3. Select the listed start cell before using File -> Import.",
            "4. Choose the CSV from this import pack.",
            "5. For gate/template/model CSVs, use Replace data at selected cell.",
            "6. Do not overwrite formula or summary sections unless intentionally refreshing those formulas.",
            "",
            "## Tabs That Need Extra Care",
            "",
            "- `Live Readiness`: use as review data or import into a scratch area unless you intentionally want to refresh formula-backed summary sections.",
            "- `Forward Readiness`: safe as a blockers review import, but confirm the destination area before replacing data.",
            "- `Receptions Model Test`: historical-test board only; this is not a live betting board.",
            "- `Line Ladder`: optional research import for `receptions_line_ladder.csv` at `Line Ladder!A1`. It is an odds-free probability ladder, not a betting edge.",
            "- `Line Ladder Top`: optional research import for `receptions_line_ladder_top_by_line.csv` at `Line Ladder Top!A1`. It is a top-by-line review table, not a betting edge.",
            "",
            "## Historical Test vs Forward Projection",
            "",
            "`historical_test` validates the model on historical windows and labels rows `HISTORICAL TEST ONLY`.",
            "",
            "`forward_projection` is for live/future use. It must not silently fall back to historical mode. It requires schedule, roster, role, injury, and current-team gates to be ready before projection use. Betting-edge use also requires market odds.",
            "",
            "## Why Final Live Readiness Is NO-GO",
            "",
            "The current run is blocked because the model is in historical-test mode and live gate data is incomplete. Roster, role, injury, and market odds templates still need validated data before live use.",
            "",
            "## Required Before Live Use",
            "",
            "- Switch to `projection_mode: forward_projection` only after gates are ready.",
            "- Confirm schedule for the target season/week.",
            "- Verify current roster/team for every candidate player.",
            "- Fill role confidence and starter/route context.",
            "- Fill injury/practice/game-status data.",
            "- Add market odds before treating any output as a betting-edge board.",
            "",
            "## Optional Line Ladder Imports",
            "",
            "`receptions_line_ladder.csv` imports to `Line Ladder!A1`. `receptions_line_ladder_top_by_line.csv` imports to `Line Ladder Top!A1`. These are optional research tabs, not betting edges. Odds are still required for actual edge, and historical-test output must remain labeled `HISTORICAL TEST ONLY`.",
        ]
    )
    return "\n".join(lines) + "\n"


def create_zip(files: list[Path], zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, arcname=file.name)


def build_import_pack() -> tuple[pd.DataFrame, Path, list[Path], str, list[str], bool, list[str]]:
    status_by_gate, final_status, blocked_gates, live_betting_output_exists = _read_statuses()
    warnings: list[str] = []
    required_sources = [_source_path(item["file_name"]) for item in IMPORT_ITEMS]
    missing = [path for path in required_sources if not path.exists()]
    if missing:
        warnings.extend(f"Missing source file: {path}" for path in missing)
    manifest = build_manifest()
    manifest_path = _pack_path(MANIFEST_NAME)
    instructions_path = _pack_path(INSTRUCTIONS_NAME)
    zip_path = _pack_path(ZIP_NAME)
    manifest.to_csv(manifest_path, index=False)
    instructions_path.write_text(build_instructions(manifest, final_status, blocked_gates), encoding="utf-8")
    files = [path for path in required_sources if path.exists()] + [manifest_path, instructions_path]
    create_zip(files, zip_path)
    return manifest, zip_path, files, final_status, blocked_gates, live_betting_output_exists, warnings


def main() -> None:
    manifest, zip_path, files, final_status, blocked_gates, live_betting_output_exists, warnings = build_import_pack()
    print("Import pack created")
    print("Files included")
    for file in files:
        print(f"- {file}")
    print(f"Final live readiness: {final_status}")
    print(f"Blocked gates: {', '.join(blocked_gates) if blocked_gates else 'None'}")
    print(f"Live betting output exists: {live_betting_output_exists}")
    print(f"Zip path: {zip_path}")
    if warnings:
        print("Warnings")
        for warning in warnings:
            print(f"- {warning}")
    print(f"Manifest rows: {len(manifest)}")


if __name__ == "__main__":
    main()
