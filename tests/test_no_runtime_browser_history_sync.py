from pathlib import Path


def test_browser_history_sync_is_never_invoked_by_dashboard_pages() -> None:
    offenders: list[str] = []
    for path in Path("dashboard").rglob("*.py"):
        if path.name == "control_state.py":
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped == "enable_browser_history_sync()":
                offenders.append(f"{path}:{line_number}")
    assert not offenders, "runtime history-sync calls remain: " + ", ".join(offenders)
