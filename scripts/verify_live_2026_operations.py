from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import Frame, Page, sync_playwright

LIVE = "https://propwar.streamlit.app"
OUT = Path("outputs/live_2026_operations_verification")
SHOTS = OUT / "screenshots"


def find_frame(page: Page, text: str) -> Frame | None:
    for frame in page.frames:
        try:
            if frame.get_by_text(text, exact=False).count():
                return frame
        except Exception:
            continue
    return None


def wake_if_sleeping(page: Page) -> bool:
    try:
        body = page.locator("body").inner_text(timeout=5000)
    except Exception:
        return False
    if "gone to sleep due to inactivity" not in body:
        return False
    button = page.get_by_text("Yes, get this app back up!", exact=True)
    if button.count():
        button.first.click()
        page.wait_for_timeout(3000)
        return True
    return False


def frame_diagnostics(page: Page) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for frame in page.frames:
        try:
            body = frame.locator("body").inner_text(timeout=5000)[:6000]
        except Exception as exc:
            body = f"<body unavailable: {exc}>"
        rows.append({"url": frame.url, "body": body})
    return rows


def verify(
    page: Page,
    path: str,
    anchor: str,
    required: tuple[str, ...],
    forbidden: tuple[str, ...] = (),
    wait_seconds: int = 150,
) -> dict[str, object]:
    name = path.strip("/") or "home"
    navigation_error = ""
    woke = False
    try:
        page.goto(LIVE + path, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        navigation_error = str(exc)
    woke = wake_if_sleeping(page)

    frame: Frame | None = None
    for _ in range(wait_seconds):
        frame = find_frame(page, anchor)
        if frame is not None:
            body = frame.locator("body").inner_text()
            if all(value in body for value in required):
                break
        if wake_if_sleeping(page):
            woke = True
        time.sleep(1)

    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
    diagnostics = frame_diagnostics(page)
    if frame is None:
        return {
            "path": path,
            "status": "FAIL",
            "reason": f"anchor not found: {anchor}",
            "navigation_error": navigation_error,
            "woke_app": woke,
            "frames": diagnostics,
        }

    body = frame.locator("body").inner_text()
    missing = [value for value in required if value not in body]
    unexpected = [value for value in forbidden if value in body]
    return {
        "path": path,
        "status": "PASS" if not missing and not unexpected else "FAIL",
        "missing": missing,
        "unexpected": unexpected,
        "navigation_error": navigation_error,
        "woke_app": woke,
        "frame_url": frame.url,
        "frames": diagnostics,
    }


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        results = [
            verify(
                page,
                "/",
                "Know what changed before researching what happens next.",
                (
                    "Backfield Control",
                    "Target Hierarchy",
                    "Role Movement",
                    "2026 current-season role data will publish after the first fully completed regular-season week",
                ),
            ),
            verify(
                page,
                "/reports",
                "NFL Role Intelligence",
                (
                    "Backfield Control",
                    "Target Hierarchy",
                    "Role Movement",
                    "All-play evidence",
                    "Complete report",
                    "2026 current-season role data will publish after the first fully completed regular-season week",
                ),
                ("Scoring-Area Usage", "Game-Script Usage", "Opportunity Versus Production"),
                wait_seconds=240,
            ),
            verify(
                page,
                "/methodology",
                "Methodology",
                (
                    "Launch report contract",
                    "Calculation authority",
                    "Report boundaries",
                    "Missing and unavailable data",
                ),
            ),
        ]
        browser.close()

    payload = {
        "live_url": LIVE,
        "production_commit": "3c6381bc6771162df0429ab23cd327cbdad3e4f5",
        "results": results,
        "status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
