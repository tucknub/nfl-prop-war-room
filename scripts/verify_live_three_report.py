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


def wait_for_deployed(page: Page, path: str, heading: str, attempts: int = 24) -> Frame:
    url = LIVE + path
    last_text = ""
    for _ in range(attempts):
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        for _ in range(60):
            frame = find_frame(page, heading)
            if frame is not None:
                return frame
            time.sleep(1)
        try:
            last_text = page.locator("body").inner_text()[:1000]
        except Exception:
            last_text = ""
        time.sleep(15)
    raise RuntimeError(f"Live deployment did not expose heading {heading!r} at {url}. Last body: {last_text}")


def verify_page(page: Page, path: str, heading: str, required: tuple[str, ...], forbidden: tuple[str, ...] = ()) -> dict[str, object]:
    frame = wait_for_deployed(page, path, heading)
    text = frame.locator("body").inner_text()
    missing = [value for value in required if value not in text]
    unexpected = [value for value in forbidden if value in text]
    name = path.strip("/") or "home"
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
    return {
        "path": path,
        "heading": heading,
        "missing": missing,
        "unexpected": unexpected,
        "frame_url": frame.url,
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

    payload = {"live_url": LIVE, "results": results, "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
