from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Frame, Page, sync_playwright

LIVE = "https://propwar.streamlit.app"
OUT = Path("outputs/live_usability_phase1_verification")
SHOTS = OUT / "screenshots"
REPORTS = ("Backfield Control", "Target Hierarchy", "Role Movement")


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


def diagnostics(page: Page) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for frame in page.frames:
        try:
            body = frame.locator("body").inner_text(timeout=5000)[:5000]
        except Exception as exc:
            body = f"<body unavailable: {exc}>"
        rows.append({"url": frame.url, "body": body})
    return rows


def wait_for_content(
    page: Page,
    path: str,
    anchor: str,
    required: tuple[str, ...],
    *,
    wait_seconds: int,
) -> tuple[Frame | None, bool, str]:
    navigation_error = ""
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
    return frame, woke, navigation_error


def direct_report_links(frame: Frame) -> dict[str, str | None]:
    links: dict[str, str | None] = {}
    for report in REPORTS:
        locator = frame.get_by_role("link", name=f"View {report}", exact=True)
        links[report] = locator.first.get_attribute("href") if locator.count() else None
    return links


def valid_report_href(href: str | None, report: str) -> bool:
    if not href:
        return False
    parsed = urlsplit(href)
    return parsed.path.endswith("/reports") and parse_qs(parsed.query).get("report", [""])[0] == report


def verify_viewport(width: int, height: int, name: str) -> dict[str, object]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        results: list[dict[str, object]] = []

        home_required = (
            "What changed in NFL roles?",
            "View Backfield Control",
            "View Target Hierarchy",
            "View Role Movement",
            "This Week in NFL Roles",
        )
        frame, woke, error = wait_for_content(page, "/", "What changed in NFL roles?", home_required, wait_seconds=180)
        home_links = direct_report_links(frame) if frame is not None else {}
        home_failures = [value for value in home_required if frame is None or value not in frame.locator("body").inner_text()]
        for report, href in home_links.items():
            if not valid_report_href(href, report):
                home_failures.append(f"invalid direct link for {report}: {href}")
        page.screenshot(path=str(SHOTS / f"{name}_home.png"), full_page=True)
        results.append({
            "page": "Home",
            "status": "PASS" if not home_failures else "FAIL",
            "failures": home_failures,
            "links": home_links,
            "woke_app": woke,
            "navigation_error": error,
        })

        reports_required = (
            "NFL Role Intelligence",
            "Backfield Control",
            "Customize report",
            "Top findings",
            "Team share",
            "Opportunities",
            "Complete report",
            "Show all evidence columns",
        )
        frame, woke, error = wait_for_content(page, "/reports?report=Backfield%20Control", "NFL Role Intelligence", reports_required, wait_seconds=260)
        reports_body = frame.locator("body").inner_text() if frame is not None else ""
        reports_failures = [value for value in reports_required if value not in reports_body]
        for retired in ("Scoring-Area Usage", "Game-Script Usage", "Opportunity Versus Production"):
            if retired in reports_body:
                reports_failures.append(f"retired report visible: {retired}")
        page.screenshot(path=str(SHOTS / f"{name}_reports.png"), full_page=True)
        results.append({
            "page": "Reports",
            "status": "PASS" if not reports_failures else "FAIL",
            "failures": reports_failures,
            "woke_app": woke,
            "navigation_error": error,
        })

        methodology_required = (
            "Methodology",
            "How to read a report",
            "Plain-language terms",
            "Backfield Control",
            "Target Hierarchy",
            "Role Movement",
            "Report boundaries",
            "Calculation details",
        )
        frame, woke, error = wait_for_content(page, "/methodology", "Methodology", methodology_required, wait_seconds=180)
        methodology_body = frame.locator("body").inner_text() if frame is not None else ""
        methodology_failures = [value for value in methodology_required if value not in methodology_body]
        page.screenshot(path=str(SHOTS / f"{name}_methodology.png"), full_page=True)
        results.append({
            "page": "Methodology",
            "status": "PASS" if not methodology_failures else "FAIL",
            "failures": methodology_failures,
            "woke_app": woke,
            "navigation_error": error,
        })

        dimensions = page.evaluate("""() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
        })""")
        relevant_console = [message for message in console_errors if "/_stcore/" not in message and "favicon" not in message.lower()]
        payload = {
            "viewport": f"{width}x{height}",
            "results": results,
            "overflow": dimensions["overflow"],
            "console_errors": relevant_console,
            "page_errors": page_errors,
            "frames": diagnostics(page),
        }
        payload["status"] = "PASS" if all(item["status"] == "PASS" for item in results) and dimensions["overflow"] <= 1 and not relevant_console and not page_errors else "FAIL"
        browser.close()
        return payload


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    mobile = verify_viewport(390, 844, "mobile")
    desktop = verify_viewport(1440, 900, "desktop")
    payload = {
        "live_url": LIVE,
        "production_commit": "53dafdbae598570ab236ba0355ddcef7830e7537",
        "mobile": mobile,
        "desktop": desktop,
        "status": "PASS" if mobile["status"] == desktop["status"] == "PASS" else "FAIL",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
