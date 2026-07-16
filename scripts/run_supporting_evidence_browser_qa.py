from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "supporting_evidence_experience"
SHOTS = OUT / "screenshots"
sys.path.insert(0, str(ROOT / "scripts"))
from run_control_state_browser_qa import LocalRouteProxy  # noqa: E402


HEADINGS = {
    "/": "This Week in NFL Roles", "/teams": "Team Role Breakdown",
    "/players": "Player Role Profile", "/games": "Game Usage Review",
    "/reports": "Research Reports", "/explorer": "Advanced Research",
}


def body(page: Page) -> str:
    return page.locator("body").inner_text()


def wait_heading(page: Page, route: str) -> None:
    page.get_by_role("heading", name=HEADINGS[route], exact=True).wait_for(timeout=90000)
    page.wait_for_timeout(1200)


def goto(page: Page, base: str, route: str, query: str = "") -> None:
    page.goto(base, wait_until="domcontentloaded", timeout=90000)
    wait_heading(page, "/")
    if route != "/":
        page.locator(f'a[href="{base}{route}"]').evaluate("element => element.click()")
        wait_heading(page, route)
    if query:
        page.goto(f"{base}{route}?{query}", wait_until="domcontentloaded", timeout=90000)
        wait_heading(page, route)


def dimensions(page: Page) -> dict[str, int]:
    return page.evaluate("""() => ({width: innerWidth, client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth, overflow: document.documentElement.scrollWidth-innerWidth})""")


def choose(page: Page, label: str, value: str) -> None:
    control = page.get_by_role("combobox", name=re.compile(label, re.I)).first
    control.click()
    control.fill(value)
    control.press("Enter")
    page.wait_for_timeout(1800)


def open_text(page: Page, label: str) -> None:
    page.get_by_text(label, exact=True).click()
    page.wait_for_timeout(350)


def check_page(page: Page, route: str, failures: list[str], overflow: list[str]) -> None:
    text = body(page)
    if "Exception" in text or "Traceback" in text:
        failures.append(f"{route}: exception overlay")
    if dimensions(page)["overflow"] != 0:
        overflow.append(route)


def run_viewport(browser, base: str, width: int, height: int, name: str) -> dict[str, object]:
    page = browser.new_page(viewport={"width": width, "height": height})
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(f"{message.text} [{message.location.get('url', '')}]") if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    failures: list[str] = []
    overflow: list[str] = []

    goto(page, base, "/", "season=2025&week=17")
    if name == "mobile": page.screenshot(path=str(SHOTS / "mobile_home_to_team.png"))
    else: page.screenshot(path=str(SHOTS / "desktop_home.png"))
    check_page(page, "Home", failures, overflow)

    # Home -> Team, Back, Player, Back, Game verifies the complete evidence chain.
    team_href = page.get_by_role("link", name="Team Role Breakdown").first.get_attribute("href")
    player_href = page.get_by_role("link", name="Player Profile").first.get_attribute("href")
    game_href = page.get_by_role("link", name="Game Usage Review").first.get_attribute("href")
    parsed = urlsplit(str(team_href))
    goto(page, base, parsed.path, parsed.query)
    page.get_by_text("Role hierarchy at a glance", exact=True).wait_for(timeout=90000)
    page.wait_for_timeout(3000)
    team_text = body(page)
    if "DAL · 2025" not in team_text or "Role hierarchy at a glance" not in team_text: failures.append(f"{name}: Home Team evidence state")
    if name == "mobile":
        page.screenshot(path=str(SHOTS / "mobile_team_hierarchy.png"))
    else: page.screenshot(path=str(SHOTS / "desktop_teams.png"))
    check_page(page, "Teams", failures, overflow)
    parsed = urlsplit(str(player_href))
    goto(page, base, parsed.path, parsed.query)
    player_text = body(page)
    if "What role does this player currently have" not in player_text or "Team comparison" not in player_text: failures.append(f"{name}: Home Player evidence state")
    if name == "mobile":
        page.screenshot(path=str(SHOTS / "mobile_home_to_player.png"))
        page.get_by_text("Weekly opportunity", exact=True).scroll_into_view_if_needed(); page.screenshot(path=str(SHOTS / "mobile_player_chart.png"))
        page.get_by_role("heading", name="Player Role Profile", exact=True).scroll_into_view_if_needed(); page.screenshot(path=str(SHOTS / "mobile_player_summary.png"))
    else: page.screenshot(path=str(SHOTS / "desktop_players.png"))
    check_page(page, "Players", failures, overflow)
    parsed = urlsplit(str(game_href))
    goto(page, base, parsed.path, parsed.query)
    page.get_by_text("Team opportunity totals", exact=True).wait_for(timeout=90000)
    game_text = body(page)
    if "DAL at WAS" not in game_text or "Team opportunity totals" not in game_text:
        failures.append(f"{name}: Home Game evidence state")
    if "2025_17_DAL_WAS · Week" in game_text: failures.append(f"{name}: internal game ID used as primary title")
    if name == "mobile":
        page.screenshot(path=str(SHOTS / "mobile_home_to_game.png"))
        page.get_by_text("DAL player usage", exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(SHOTS / "mobile_game_summary.png"))
    else: page.screenshot(path=str(SHOTS / "desktop_games.png"))
    check_page(page, "Games", failures, overflow)
    page.go_back(wait_until="domcontentloaded"); page.wait_for_timeout(1200)
    page.go_forward(wait_until="domcontentloaded"); wait_heading(page, "/games")
    if "game=2025_17_DAL_WAS" not in page.url: failures.append(f"{name}: Back/Forward lost Game state")

    goto(page, base, "/reports")
    report_names = ["Backfield Control", "Target Hierarchy", "Scoring-Area Usage", "Role Movement", "Opportunity Versus Production", "Game-Script Usage"]
    for report in report_names:
        choose(page, "Research question", report)
        if report not in body(page) or "Top factual findings" not in body(page): failures.append(f"{name}: report {report}")
    if name == "mobile": page.screenshot(path=str(SHOTS / "mobile_reports.png"))
    else: page.screenshot(path=str(SHOTS / "desktop_reports.png"))
    check_page(page, "Reports", failures, overflow)

    goto(page, base, "/explorer")
    open_text(page, "Start with a verified preset")
    choose(page, "Preset", "Targets while trailing")
    page.get_by_role("button", name="Apply preset").click(); page.wait_for_timeout(2200)
    if "Trailing" not in body(page) or "WR target share" not in body(page): failures.append(f"{name}: Explorer preset")
    open_text(page, "Change filters")
    if page.get_by_role("button", name="Reset filters").count() != 1: failures.append(f"{name}: Explorer Reset inaccessible")
    page.get_by_role("button", name="Reset filters").click(); page.wait_for_timeout(2200)
    reset = body(page)
    if "Minimum 5" not in reset or "Normal game" not in reset or "Trailing" in reset.split("Conditions:", 1)[-1].split("Comparison:", 1)[0]: failures.append(f"{name}: Explorer Reset defaults")
    if name == "mobile": page.screenshot(path=str(SHOTS / "mobile_explorer_presets.png"))
    else: page.screenshot(path=str(SHOTS / "desktop_explorer.png"))
    check_page(page, "Explorer", failures, overflow)

    relevant_console = [message for message in console_errors if "/_stcore/" not in message and "favicon" not in message.lower()]
    result = {
        "status": "PASS" if not failures and not overflow and not relevant_console and not page_errors else "FAIL",
        "viewport": f"{width}x{height}", "dimensions": dimensions(page),
        "routes": ["Home", "Teams", "Players", "Games", "Reports", "Explorer"],
        "overflow_failures": overflow, "workflow_failures": failures,
        "console_errors": relevant_console, "page_errors": page_errors,
    }
    page.close()
    return result


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    proxy = LocalRouteProxy("127.0.0.1", 8514, 8516)
    proxy.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            mobile = run_viewport(browser, "http://127.0.0.1:8516", 390, 844, "mobile")
            desktop = run_viewport(browser, "http://127.0.0.1:8516", 1440, 900, "desktop")
            browser.close()
    finally:
        proxy.stop()
    payload = {"mobile": mobile, "desktop": desktop}
    (OUT / "browser_results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for name, result in payload.items():
        (OUT / f"{name}_qa.md").write_text(
            f"# {name.title()} QA\n\n- Viewport: {result['viewport']}\n- Status: {result['status']}\n- Horizontal overflow: {len(result['overflow_failures'])}\n- Workflow failures: {len(result['workflow_failures'])}\n- Console errors: {len(result['console_errors'])}\n- Page errors: {len(result['page_errors'])}\n- Routes: {', '.join(result['routes'])}\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, indent=2))
    return 0 if mobile["status"] == desktop["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
