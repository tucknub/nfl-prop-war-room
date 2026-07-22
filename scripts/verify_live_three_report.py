from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import Frame, Page, sync_playwright

LIVE = "https://propwar.streamlit.app"
OUT = Path("outputs/live_three_report_verification")
SHOTS = OUT / "screenshots"


def find_frame(page: Page, heading: str) -> Frame | None:
    for frame in page.frames:
        try:
            if frame.get_by_role("heading", name=heading, exact=True).count():
                return frame
        except Exception:
            continue
    return None


def frame_diagnostics(page: Page) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    for frame in page.frames:
        try:
            text = frame.locator("body").inner_text(timeout=5000)[:2000]
        except Exception as exc:
            text = f"<body unavailable: {exc}>"
        diagnostics.append({"url": frame.url, "body": text})
    return diagnostics


def verify_page(
    page: Page,
    path: str,
    heading: str,
    required: tuple[str, ...],
    forbidden: tuple[str, ...] = (),
) -> dict[str, object]:
    name = path.strip("/") or "home"
    url = LIVE + path
    frame: Frame | None = None
    navigation_errors: list[str] = []

    for attempt in range(1, 4):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
        except Exception as exc:
            navigation_errors.append(f"attempt {attempt}: {exc}")
        for _ in range(30):
            frame = find_frame(page, heading)
            if frame is not None:
                break
            time.sleep(1)
        if frame is not None:
            break
        page.reload(wait_until="domcontentloaded", timeout=90000)

    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
    diagnostics = frame_diagnostics(page)
    if frame is None:
        return {
            "path": path,
            "heading": heading,
            "status": "FAIL",
            "reason": "expected heading not found",
            "navigation_errors": navigation_errors,
            "frames": diagnostics,
        }

    text = frame.locator("body").inner_text()
    missing = [value for value in required if value not in text]
    unexpected = [value for value in forbidden if value in text]
    return {
        "path": path,
        "heading": heading,
        "frame_url": frame.url,
        "missing": missing,
        "unexpected": unexpected,
        "navigation_errors": navigation_errors,
        "frames": diagnostics,
        "status": "PASS" if not missing and not unexpected else "FAIL",
    }


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        results = [
            verify_page(
                page,
                "/",
                "Know what changed before researching what happens next.",
                ("Backfield Control", "Target Hierarchy", "Role Movement", "Open Reports"),
            ),
            verify_page(
                page,
                "/reports",
                "NFL Role Intelligence",
                ("Backfield Control", "Target Hierarchy", "Role Movement", "All-play evidence", "Complete report"),
                ("Scoring-Area Usage", "Game-Script Usage", "Opportunity Versus Production"),
            ),
            verify_page(
                page,
                "/methodology",
                "Methodology",
                ("Launch report contract", "Calculation authority", "Report boundaries", "Missing and unavailable data"),
            ),
        ]
        browser.close()

    payload = {
        "live_url": LIVE,
        "results": results,
        "status": "PASS" if all(result["status"] == "PASS" for result in results) else "FAIL",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
