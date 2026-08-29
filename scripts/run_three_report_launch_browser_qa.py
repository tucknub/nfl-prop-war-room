from __future__ import annotations

import json
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Locator, Page, sync_playwright

from run_control_state_browser_qa import LocalRouteProxy as BaseLocalRouteProxy


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "three_report_browser_qa"
SHOTS = OUT / "screenshots"

HOME_HEADINGS = ("What changed in NFL roles?", "Latest NFL role research")
REPORT_HEADING = "NFL Role Intelligence"
METHODOLOGY_HEADING = "Methodology"
REPORTS = ("Backfield Control", "Target Hierarchy", "Role Movement")
RETIRED_REPORTS = (
    "Scoring-Area Usage",
    "Game-Script Usage",
    "Opportunity Versus Production",
)
METHODOLOGY_COPY = (
    "All-play raw counts and same-team denominators are the methodology authority",
    "How to read a report",
    "Backfield Control",
    "Target Hierarchy",
    "Role Movement",
    "Plain-language terms",
    "Report boundaries",
    "Missing and unavailable data",
)


class LocalRouteProxy(BaseLocalRouteProxy):
    _subpages = BaseLocalRouteProxy._subpages | {"methodology"}


def body(page: Page) -> str:
    return page.locator("body").inner_text()


def dimensions(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
        })"""
    )


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def first_visible(locator: Locator) -> Locator | None:
    for index in range(locator.count()):
        item = locator.nth(index)
        if item.is_visible():
            return item
    return None


def click_report(page: Page, report: str) -> None:
    candidates = (
        page.get_by_role("button", name=report, exact=True),
        page.locator('[data-testid="stSegmentedControl"]').get_by_text(report, exact=True),
        page.get_by_text(report, exact=True),
    )
    for candidate in candidates:
        item = first_visible(candidate)
        if item is not None:
            item.click()
            page.wait_for_timeout(1800)
            page.get_by_role("heading", name=report, exact=True).wait_for(timeout=90000)
            return
    raise RuntimeError(f"Could not activate report: {report}")


def wait_for_home_heading(page: Page) -> None:
    for _ in range(180):
        for heading in HOME_HEADINGS:
            locator = page.get_by_role("heading", name=heading, exact=True)
            if locator.count() and locator.first.is_visible():
                return
        page.wait_for_timeout(500)
    raise RuntimeError(f"Home heading not found; expected one of: {HOME_HEADINGS}")


def goto_root(page: Page, base: str) -> None:
    page.goto(base, wait_until="domcontentloaded", timeout=90000)
    wait_for_home_heading(page)
    page.wait_for_timeout(1200)


def navigate(page: Page, base: str, route: str, heading: str) -> None:
    """Navigate through an available Streamlit page route.

    Top-navigation child links may be lazily rendered inside a menu. Prefer the live
    navigation link when present; otherwise exercise the registered route directly.
    """
    goto_root(page, base)
    locator = page.locator(f'a[href="{base}/{route}"]')
    if locator.count() == 0:
        locator = page.locator(f'a[href="/{route}"]')
    if locator.count() > 0:
        locator.first.evaluate("element => element.click()")
    else:
        page.goto(f"{base}/{route}", wait_until="domcontentloaded", timeout=90000)
    page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=90000)
    page.wait_for_timeout(1500)


def validate_report_href(href: str | None, report: str) -> bool:
    if not href:
        return False
    parsed = urlsplit(href)
    query = parse_qs(parsed.query)
    return parsed.path.endswith("/reports") and query.get("report", [""])[0] == report


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


def verify_team_history_sync(page: Page, base: str, name: str, failures: list[str]) -> None:
    page.goto(
        f"{base}/teams?team=DAL&season=2025&family=rb_opportunity_share&week=17",
        wait_until="domcontentloaded",
        timeout=90000,
    )
    page.get_by_role("heading", name="Team Role Breakdown", exact=True).wait_for(timeout=90000)
    page.get_by_text("Change filters", exact=True).click()
    team_box = page.get_by_role("combobox", name="Search or select team").first
    team_box.click()
    team_box.fill("PHI")
    team_box.press("Enter")
    page.wait_for_timeout(1800)

    check("team=PHI" in page.url, f"{name}: Teams selection did not update URL", failures)

    page.go_back(wait_until="domcontentloaded")
    page.get_by_role("heading", name="Team Role Breakdown", exact=True).wait_for(timeout=90000)
    page.wait_for_timeout(1800)
    check("team=DAL" in page.url, f"{name}: browser Back did not restore DAL URL", failures)
    check("DAL · 2025" in body(page), f"{name}: browser Back did not restore DAL content", failures)

    page.go_forward(wait_until="domcontentloaded")
    page.get_by_role("heading", name="Team Role Breakdown", exact=True).wait_for(timeout=90000)
    page.wait_for_timeout(1800)
    check("team=PHI" in page.url, f"{name}: browser Forward did not restore PHI URL", failures)
    check("PHI · 2025" in body(page), f"{name}: browser Forward did not restore PHI content", failures)


def record_page_state(page: Page, label: str, failures: list[str], overflow: list[str]) -> None:
    text = body(page)
    if any(marker in text for marker in ("Traceback", "Exception", "This app has encountered an error")):
        failures.append(f"{label}: application error visible")
    if dimensions(page)["overflow"] > 1:
        overflow.append(label)


def desktop_top_navigation_visible(page: Page) -> bool:
    """Desktop must expose a visible Streamlit header and top navigation group."""
    header = first_visible(page.locator('[data-testid="stHeader"]'))
    if header is None:
        return False
    role_group = first_visible(page.get_by_text("Role Intelligence", exact=True))
    return role_group is not None


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

    goto_root(page, base)
    if name == "desktop":
        check(
            desktop_top_navigation_visible(page),
            f"{name}: native top navigation is not visibly available",
            failures,
        )
    home_text = body(page)
    for report in REPORTS:
        check(report in home_text, f"{name}: Home missing {report}", failures)
    check("View Backfield Control" in home_text, f"{name}: Home missing direct report CTA", failures)
    home_cta = first_visible(page.get_by_role("link", name="View Backfield Control", exact=True))
    home_href = home_cta.get_attribute("href") if home_cta is not None else None
    check(
        validate_report_href(home_href, "Backfield Control"),
        f"{name}: invalid direct report link: {home_href}",
        failures,
    )
    page.screenshot(path=str(SHOTS / f"{name}_home.png"), full_page=True)
    record_page_state(page, "Home", failures, overflow)
    routes.append("Home")

    navigate(page, base, "reports", REPORT_HEADING)
    report_text = body(page)
    for report in REPORTS:
        check(report in report_text, f"{name}: Reports missing {report}", failures)
    for retired in RETIRED_REPORTS:
        check(retired not in report_text, f"{name}: retired report visible: {retired}", failures)

    for report in REPORTS:
        click_report(page, report)
        text = body(page)
        check("Top findings" in text, f"{name}: {report} missing top findings", failures)
        check("Complete report" in text, f"{name}: {report} missing complete table", failures)
        check("All-play evidence" in text, f"{name}: {report} missing all-play evidence", failures)
        check("View player evidence" in text, f"{name}: {report} missing player evidence link", failures)
        check("View team evidence" in text, f"{name}: {report} missing team evidence link", failures)
        page.screenshot(
            path=str(SHOTS / f"{name}_{report.lower().replace(' ', '_')}.png"),
            full_page=True,
        )
        record_page_state(page, f"Reports/{report}", failures, overflow)
    routes.append("Reports")

    click_report(page, "Backfield Control")
    evidence_link = first_visible(page.get_by_role("link", name="View player evidence", exact=True))
    href = evidence_link.get_attribute("href") if evidence_link is not None else None
    check(validate_player_href(href), f"{name}: invalid Player evidence deep link: {href}", failures)
    routes.append("Player evidence link contract")

    navigate(page, base, "methodology", METHODOLOGY_HEADING)
    methodology_text = body(page)
    for phrase in METHODOLOGY_COPY:
        check(phrase in methodology_text, f"{name}: Methodology missing {phrase}", failures)
    page.screenshot(path=str(SHOTS / f"{name}_methodology.png"), full_page=True)
    record_page_state(page, "Methodology", failures, overflow)
    routes.append("Methodology")

    if name == "mobile":
        verify_team_history_sync(page, base, name, failures)
        routes.append("Browser Back/Forward")

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
        "dimensions": dimensions(page),
        "workflow_failures": failures,
        "overflow_failures": overflow,
        "console_errors": relevant_console,
        "page_errors": page_errors,
    }
    page.close()
    return result


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    proxy = LocalRouteProxy("127.0.0.1", 8514, 8516)
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

    OUT.mkdir(parents=True, exist_ok=True)
    target = "browser_results.json" if "mobile" in payload else "browser_crash.json"
    (OUT / target).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if "mobile" not in payload:
        return 1
    return 0 if payload["mobile"]["status"] == payload["desktop"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
