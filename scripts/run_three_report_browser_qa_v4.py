from __future__ import annotations

import json
import traceback
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page, sync_playwright

import run_three_report_browser_qa as qa
from run_three_report_browser_qa_v2 import navigate


def record_page_state(page: Page, label: str, failures: list[str], overflow: list[str]) -> None:
    text = qa.body(page)
    if any(marker in text for marker in ("Traceback", "Exception", "This app has encountered an error")):
        failures.append(f"{label}: application error visible")
    if qa.dimensions(page)["overflow"] > 1:
        overflow.append(label)


def validate_player_href(href: str | None) -> bool:
    if not href:
        return False
    parsed = urlsplit(href)
    query = parse_qs(parsed.query)
    return (
        parsed.path.endswith("/players")
        and bool(query.get("player", [""])[0])
        and query.get("season", [""])[0] == "2025"
        and bool(query.get("family", [""])[0])
        and bool(query.get("week", [""])[0])
    )


def run_viewport(browser, base: str, width: int, height: int, name: str) -> dict[str, object]:
    page = browser.new_page(viewport={"width": width, "height": height})
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on(
        "console",
        lambda message: console_errors.append(
            f"{message.text} [{message.location.get('url', '')}]"
        )
        if message.type == "error"
        else None,
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    failures: list[str] = []
    overflow: list[str] = []
    routes: list[str] = []

    qa.goto_root(page, base)
    home_text = qa.body(page)
    for report in qa.REPORTS:
        qa.check(report in home_text, f"{name}: Home missing {report}", failures)
    qa.check("Open Reports" in home_text, f"{name}: Home missing report CTA", failures)
    page.screenshot(path=str(qa.SHOTS / f"{name}_home.png"), full_page=True)
    record_page_state(page, "Home", failures, overflow)
    routes.append("Home")

    navigate(page, base, "Reports", qa.REPORT_HEADING)
    report_text = qa.body(page)
    for report in qa.REPORTS:
        qa.check(report in report_text, f"{name}: Reports missing {report}", failures)
    for retired in qa.RETIRED_REPORTS:
        qa.check(retired not in report_text, f"{name}: retired report visible: {retired}", failures)

    for report in qa.REPORTS:
        qa.click_report(page, report)
        text = qa.body(page)
        qa.check("Answer first" in text, f"{name}: {report} missing Answer first", failures)
        qa.check("Complete report" in text, f"{name}: {report} missing complete table", failures)
        qa.check("All-play evidence" in text, f"{name}: {report} missing all-play evidence", failures)
        qa.check("Player evidence" in text, f"{name}: {report} missing player evidence link", failures)
        qa.check("Team evidence" in text, f"{name}: {report} missing team evidence link", failures)
        page.screenshot(
            path=str(qa.SHOTS / f"{name}_{report.lower().replace(' ', '_')}.png"),
            full_page=True,
        )
        record_page_state(page, f"Reports/{report}", failures, overflow)
    routes.append("Reports")

    qa.click_report(page, "Backfield Control")
    evidence_link = qa.first_visible(page.get_by_role("link", name="Player evidence", exact=True))
    href = evidence_link.get_attribute("href") if evidence_link is not None else None
    qa.check(validate_player_href(href), f"{name}: invalid Player evidence deep link: {href}", failures)
    routes.append("Player evidence link contract")

    navigate(page, base, "Methodology", qa.METHODOLOGY_HEADING)
    methodology_text = qa.body(page)
    for required in (
        "All-play values are authoritative",
        "Backfield Control",
        "Target Hierarchy",
        "Role Movement",
        "Missing-data behavior",
        "What the reports do not claim",
    ):
        qa.check(required in methodology_text, f"{name}: Methodology missing {required}", failures)
    page.screenshot(path=str(qa.SHOTS / f"{name}_methodology.png"), full_page=True)
    record_page_state(page, "Methodology", failures, overflow)
    routes.append("Methodology")

    relevant_console = [
        message
        for message in console_errors
        if "/_stcore/" not in message and "favicon" not in message.lower()
    ]
    result = {
        "status": "PASS"
        if not failures and not overflow and not relevant_console and not page_errors
        else "FAIL",
        "viewport": f"{width}x{height}",
        "routes": routes,
        "dimensions": qa.dimensions(page),
        "workflow_failures": failures,
        "overflow_failures": overflow,
        "console_errors": relevant_console,
        "page_errors": page_errors,
    }
    page.close()
    return result


def main() -> int:
    qa.SHOTS.mkdir(parents=True, exist_ok=True)
    proxy = qa.LocalRouteProxy("127.0.0.1", 8514, 8516)
    proxy.start()
    payload: dict[str, object]
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            mobile = run_viewport(browser, "http://127.0.0.1:8516", 390, 844, "mobile")
            desktop = run_viewport(browser, "http://127.0.0.1:8516", 1440, 900, "desktop")
            browser.close()
        payload = {"mobile": mobile, "desktop": desktop}
    except Exception as error:
        payload = {
            "status": "CRASH",
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
    finally:
        proxy.stop()

    qa.OUT.mkdir(parents=True, exist_ok=True)
    target = "browser_results.json" if "mobile" in payload else "browser_crash.json"
    (qa.OUT / target).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if "mobile" not in payload:
        return 1
    return 0 if payload["mobile"]["status"] == payload["desktop"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
