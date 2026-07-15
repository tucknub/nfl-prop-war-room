from __future__ import annotations

import argparse
import asyncio
import http.client
import json
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Page, sync_playwright


HEADINGS = {
    "/": "This Week in NFL Roles",
    "/teams": "Team Opportunity Map",
    "/players": "Player Role Profile",
    "/games": "Game Usage Box Score",
    "/reports": "Usage Reports",
    "/explorer": "Usage Explorer",
}


class LocalRouteProxy:
    """Normalize Streamlit's relative subpage assets for exact local hard-refresh QA."""

    _subpages = {"teams", "players", "games", "reports", "explorer"}
    _root_resources = {"_stcore", "static", "favicon.png", "vendor"}

    def __init__(self, upstream_host: str, upstream_port: int, listen_port: int) -> None:
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.listen_port = listen_port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: asyncio.Server | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    @classmethod
    def _rewrite_target(cls, target: str) -> str:
        if target.startswith(("http://", "https://")):
            parsed = urlsplit(target)
            target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        path, separator, query = target.partition("?")
        pieces = path.lstrip("/").split("/")
        if len(pieces) >= 2 and pieces[0] in cls._subpages and pieces[1] in cls._root_resources:
            path = "/" + "/".join(pieces[1:])
        return path + (separator + query if separator else "")

    async def _pipe(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while chunk := await reader.read(65536):
                writer.write(chunk)
                await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            try:
                writer.close()
            except RuntimeError:
                pass

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            lines = header.decode("latin-1").split("\r\n")
            method, target, version = lines[0].split(" ", 2)
            lines[0] = f"{method} {self._rewrite_target(target)} {version}"
            normalized: list[str] = [lines[0]]
            for line in lines[1:]:
                lower = line.lower()
                if lower.startswith("host:"):
                    line = f"Host: {self.upstream_host}:{self.upstream_port}"
                elif lower.startswith("origin:"):
                    line = f"Origin: http://{self.upstream_host}:{self.upstream_port}"
                normalized.append(line)
            target_path = target.partition("?")[0].strip("/")
            is_subpage_html = method == "GET" and target_path in self._subpages
            if is_subpage_html:
                request_headers = {}
                for line in normalized[1:]:
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    if key.lower() not in {"accept-encoding", "connection"}:
                        request_headers[key.strip()] = value.strip()

                def fetch_html() -> bytes:
                    connection = http.client.HTTPConnection(self.upstream_host, self.upstream_port, timeout=30)
                    connection.request(method, self._rewrite_target(target), headers=request_headers)
                    response = connection.getresponse()
                    content = response.read().replace(b"<head>", b'<head><base href="/">', 1)
                    response_headers = [
                        (key, value)
                        for key, value in response.getheaders()
                        if key.lower() not in {"content-length", "transfer-encoding", "connection"}
                    ]
                    status = f"HTTP/1.1 {response.status} {response.reason}\r\n"
                    headers = "".join(f"{key}: {value}\r\n" for key, value in response_headers)
                    connection.close()
                    return (status + headers + f"Content-Length: {len(content)}\r\nConnection: close\r\n\r\n").encode(
                        "latin-1"
                    ) + content

                writer.write(await asyncio.to_thread(fetch_html))
                await writer.drain()
                writer.close()
                return
            upstream_reader, upstream_writer = await asyncio.open_connection(
                self.upstream_host, self.upstream_port
            )
            upstream_writer.write("\r\n".join(normalized).encode("latin-1"))
            await upstream_writer.drain()
            await asyncio.gather(
                self._pipe(reader, upstream_writer),
                self._pipe(upstream_reader, writer),
            )
        except (asyncio.IncompleteReadError, ConnectionError, ValueError):
            writer.close()

    def start(self) -> None:
        def run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._server = self._loop.run_until_complete(
                asyncio.start_server(self._handle, "127.0.0.1", self.listen_port)
            )
            self._ready.set()
            self._loop.run_forever()
            self._server.close()
            self._loop.run_until_complete(self._server.wait_closed())
            self._loop.close()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        if not self._ready.wait(10):
            raise RuntimeError("Local route proxy did not start")

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=10)


def choose(page: Page, label: str, value: str, wait_ms: int = 1800) -> None:
    control = page.get_by_role("combobox", name=re.compile(label, re.I)).first
    control.click()
    control.fill(value)
    control.press("Enter")
    page.wait_for_timeout(wait_ms)


def open_expander(page: Page, label: str, control_label: str) -> None:
    if page.get_by_role("combobox", name=re.compile(control_label, re.I)).count() == 0:
        page.get_by_text(label, exact=True).click()
        page.wait_for_timeout(250)


def body(page: Page) -> str:
    return page.locator("body").inner_text()


def wait_for_team_summary(page: Page, team: str, timeout: int = 15000) -> None:
    page.get_by_text(re.compile(rf"^{re.escape(team)} · 2025 · Last (?:2|4|8)$")).first.wait_for(
        timeout=timeout
    )


def metric(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          overflow: document.documentElement.scrollWidth - window.innerWidth
        })"""
    )


def prime_route(page: Page, base: str, route: str) -> None:
    if route == "/":
        page.goto(base, wait_until="domcontentloaded", timeout=90000)
        page.get_by_role("heading", name=HEADINGS[route]).wait_for(timeout=90000)
        return
    page.goto(base, wait_until="domcontentloaded", timeout=90000)
    page.get_by_role("heading", name=HEADINGS["/"]).wait_for(timeout=90000)
    page.locator(f'a[href="{base}{route}"]').evaluate("element => element.click()")
    page.get_by_role("heading", name=HEADINGS[route]).wait_for(timeout=90000)


def goto(page: Page, base: str, route: str, query: str = "") -> None:
    prime_route(page, base, route)
    if query:
        page.goto(f"{base}{route}?{query}", wait_until="domcontentloaded", timeout=90000)
        page.get_by_role("heading", name=HEADINGS[route]).wait_for(timeout=90000)
    page.wait_for_timeout(1000)


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def capture_live_before(browser, live: str, out: Path) -> dict[str, object]:
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(
        live + "/teams?team=DAL&season=2025&family=rb_opportunity_share&week=17",
        wait_until="domcontentloaded",
        timeout=90000,
    )
    app = None
    for _ in range(90):
        app = next((frame for frame in page.frames if "/~/+/teams" in frame.url), None)
        if app and app.get_by_role("heading", name="Team Opportunity Map").count():
            break
        page.wait_for_timeout(500)
    if app is None:
        raise RuntimeError("Live Streamlit frame did not load")
    app.get_by_text("Change filters", exact=True).click()
    combo = app.get_by_role("combobox", name="Team")
    combo.click()
    combo.fill("PHI")
    combo.press("Enter")
    page.wait_for_timeout(3000)
    text = app.locator("body").inner_text()
    final_url = page.url
    page.screenshot(path=str(out / "before_dal_reversion_live.png"))
    page.close()
    return {
        "url_remained_dal": "team=DAL" in final_url,
        "rendered_dal": "DAL" in text.split("Latest completed season: 2025", 1)[-1][:120],
        "attempted_selection": "PHI",
    }


def run_viewport(browser, base: str, out: Path, name: str, width: int, height: int) -> dict[str, object]:
    page = browser.new_page(viewport={"width": width, "height": height})
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on(
        "console",
        lambda msg: console_errors.append(
            f"{msg.text} [{msg.location.get('url', '')}]"
        )
        if msg.type == "error"
        else None,
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    failures: list[str] = []
    overflow: list[str] = []
    routes: list[str] = []

    # Home: two controls, query persistence, rendered summary.
    goto(page, base, "/")
    choose(page, "Week", "14")
    open_expander(page, "Change filters", "Position")
    choose(page, "Position", "RB")
    home = body(page)
    check("Week 14" in home and "RB" in home, f"{name}: Home controls", failures)
    page.screenshot(path=str(out / f"{name}_home_controls.png"))
    routes.append("Home")
    if metric(page)["overflow"] != 0:
        overflow.append("Home")

    # Teams: DAL -> PHI, second control, refresh, Back/Forward, invalid recovery.
    goto(page, base, "/teams", "team=DAL&season=2025&family=rb_opportunity_share&week=17")
    open_expander(page, "Change filters", "Search or select team")
    dal_url = page.url
    choose(page, "Search or select team", "PHI")
    choose(page, "Window", "Last 2")
    teams_text = body(page)
    check("PHI" in teams_text.split("Latest completed season: 2025", 1)[-1][:120], f"{name}: DAL to PHI", failures)
    check("team=PHI" in page.url, f"{name}: PHI query", failures)
    check("Last 2" in teams_text, f"{name}: PHI after window", failures)
    page.screenshot(path=str(out / f"{name}_dal_to_phi.png"))
    page.reload(wait_until="domcontentloaded")
    page.get_by_role("heading", name=HEADINGS["/teams"]).wait_for(timeout=90000)
    try:
        wait_for_team_summary(page, "PHI")
    except Exception:
        check(False, f"{name}: PHI refresh", failures)
    for _ in range(5):
        if "team=DAL" in page.url:
            break
        page.go_back(wait_until="domcontentloaded")
        page.wait_for_timeout(1800)
    check("team=DAL" in page.url, f"{name}: Back activates DAL URL", failures)
    try:
        wait_for_team_summary(page, "DAL")
    except Exception:
        check(False, f"{name}: Back restores DAL", failures)
    for _ in range(5):
        if "team=PHI" in page.url:
            break
        page.go_forward(wait_until="domcontentloaded")
        page.wait_for_timeout(1800)
    check("team=PHI" in page.url and page.url != dal_url, f"{name}: Forward activates PHI URL", failures)
    try:
        wait_for_team_summary(page, "PHI")
    except Exception:
        check(False, f"{name}: Forward restores PHI", failures)
    if name == "desktop":
        for team in ["MIN", "BUF", "SF", "KC", "PHI"]:
            open_expander(page, "Change filters", "Search or select team")
            choose(page, "Search or select team", team, 1200)
            check(f"team={team}" in page.url, f"desktop: team {team} query", failures)
    goto(page, base, "/teams", "team=INVALID&season=2025&family=rb_opportunity_share&week=17")
    open_expander(page, "Change filters", "Search or select team")
    check("Team not found" in body(page), f"{name}: invalid team warning", failures)
    choose(page, "Search or select team", "PHI")
    check("team=PHI" in page.url and "Team not found" not in body(page), f"{name}: invalid team recovery", failures)
    routes.append("Teams")
    if metric(page)["overflow"] != 0:
        overflow.append("Teams")

    # Players: visible search, selection persistence, multi-team labels.
    goto(page, base, "/players", "player=00-0038555&season=2025&family=rb_carry_share&week=18")
    pcombo = page.get_by_role("combobox", name=re.compile("Search or select player", re.I)).first
    pcombo.click()
    pcombo.fill("Saquon Barkley")
    page.screenshot(path=str(out / f"{name}_player_search_affordance.png"))
    pcombo.press("Enter")
    page.wait_for_timeout(1800)
    choose(page, "Role family", "RB opportunity share")
    check("Saquon Barkley" in body(page), f"{name}: player persists after family", failures)
    page.screenshot(path=str(out / f"{name}_player_persistence.png"))
    choose(page, "Search or select player", "Tank Bigsby")
    check("Tank Bigsby" in body(page) and "PHI" in body(page), f"{name}: Tank PHI label", failures)
    if name == "desktop":
        names = ["Adam Thielen", "Brandin Cooks", "Tyler Lockett", "Nick Vannett", "Marquez Valdes-Scantling", "Tank Bigsby"]
        expected = ["PIT", "BUF", "LV", "LA", "PIT", "PHI"]
        for player_name, team in zip(names, expected):
            choose(page, "Search or select player", player_name, 1200)
            check(player_name in body(page) and team in body(page), f"desktop: {player_name} {team}", failures)
    routes.append("Players")
    if metric(page)["overflow"] != 0:
        overflow.append("Players")

    # Games: dependent week/game and human-readable search.
    goto(page, base, "/games", "season=2025&week=17&game=2025_17_DAL_WAS")
    open_expander(page, "Change game", "Search or select game")
    choose(page, "Week", "18")
    game_combo = page.get_by_role("combobox", name=re.compile("Search or select game", re.I)).first
    game_combo.click()
    game_combo.fill("WAS at PHI")
    game_combo.press("Enter")
    page.wait_for_timeout(1800)
    page.screenshot(path=str(out / f"{name}_game_search_affordance.png"))
    check("week=18" in page.url and "game=2025_18_WAS_PHI" in page.url, f"{name}: game query", failures)
    check("Week 18" in body(page) and "PHI" in body(page), f"{name}: game rendered", failures)
    routes.append("Games")
    if metric(page)["overflow"] != 0:
        overflow.append("Games")

    # Reports: report/context remain after another filter.
    goto(page, base, "/reports")
    choose(page, "Report", "Game-Script Usage")
    open_expander(page, "Change filters", "Context")
    choose(page, "Context", "All plays")
    choose(page, "Period", "Last 2")
    report_text = body(page)
    check("Game-Script Usage" in report_text and "All plays" in report_text and "Last 2" in report_text, f"{name}: Reports persistence", failures)
    page.screenshot(path=str(out / f"{name}_reports_context_persistence.png"))
    routes.append("Reports")
    if metric(page)["overflow"] != 0:
        overflow.append("Reports")

    # Explorer: multiple filters and exact Reset defaults.
    goto(page, base, "/explorer")
    open_expander(page, "Change filters", "Search or select team")
    choose(page, "Search or select team", "PHI")
    choose(page, "Game state", "Leading")
    choose(page, "Quarter", "Q2")
    explorer_text = body(page)
    check("PHI" in explorer_text and "Leading" in explorer_text and "Q2" in explorer_text, f"{name}: Explorer filters", failures)
    page.screenshot(path=str(out / f"{name}_explorer_multi_filter.png"))
    page.get_by_role("button", name="Reset filters").click()
    page.wait_for_timeout(2200)
    reset_text = body(page)
    check("2025 Weeks 1–18" in reset_text and "Minimum 5;" in reset_text, f"{name}: Explorer Reset defaults", failures)
    check("Leading · Q2" not in reset_text, f"{name}: Explorer stale state after Reset", failures)
    routes.append("Explorer")
    if metric(page)["overflow"] != 0:
        overflow.append("Explorer")

    local_runtime_probes = [
        message
        for message in console_errors
        if "/_stcore/health" in message or "/_stcore/host-config" in message
    ]
    relevant_console = [
        message
        for message in console_errors
        if message not in local_runtime_probes
        and "page that you have requested" not in message.lower()
    ]
    result = {
        "status": "PASS" if not failures and not overflow and not relevant_console and not page_errors else "FAIL",
        "viewport": f"{width}x{height}",
        "routes": routes,
        "overflow_failures": len(overflow),
        "control_failures": len(failures),
        "exceptions": len(relevant_console) + len(page_errors),
        "failures": failures,
        "overflow_routes": overflow,
        "console_errors": relevant_console,
        "local_runtime_probe_404s": len(local_runtime_probes),
        "page_errors": page_errors,
        "evidence": f"{len(routes)} routes; two-or-more controls exercised on each route; screenshots in outputs/control_state_searchability/screenshots.",
    }
    page.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8514")
    parser.add_argument("--live-url", default="https://propwar.streamlit.app")
    parser.add_argument("--proxy-port", type=int, default=8515)
    args = parser.parse_args()
    out = Path(__file__).resolve().parents[1] / "outputs" / "control_state_searchability" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    upstream = urlsplit(args.base_url)
    proxy = LocalRouteProxy(upstream.hostname or "127.0.0.1", upstream.port or 80, args.proxy_port)
    proxy.start()
    local_base = f"http://127.0.0.1:{args.proxy_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--disable-gpu"])
            before = capture_live_before(browser, args.live_url.rstrip("/"), out)
            mobile = run_viewport(browser, local_base, out, "mobile", 390, 844)
            desktop = run_viewport(browser, local_base, out, "desktop", 1440, 900)
            browser.close()
    finally:
        proxy.stop()
    result = {"before": before, "mobile": mobile, "desktop": desktop}
    target = out.parent / "browser_results.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
