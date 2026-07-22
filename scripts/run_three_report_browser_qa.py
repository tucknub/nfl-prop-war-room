from __future__ import annotations

import asyncio
import http.client
import json
import threading
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Locator, Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "three_report_browser_qa"
SHOTS = OUT / "screenshots"

HOME_HEADING = "Know what changed before researching what happens next."
REPORT_HEADING = "NFL Role Intelligence"
METHODOLOGY_HEADING = "Methodology"
REPORTS = ("Backfield Control", "Target Hierarchy", "Role Movement")
RETIRED_REPORTS = (
    "Scoring-Area Usage",
    "Game-Script Usage",
    "Opportunity Versus Production",
)


class LocalRouteProxy:
    """Keep Streamlit subpage assets rooted correctly during local hard navigation."""

    _subpages = {"teams", "players", "games", "reports", "explorer", "methodology"}
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
            normalized = [lines[0]]
            for line in lines[1:]:
                lower = line.lower()
                if lower.startswith("host:"):
                    line = f"Host: {self.upstream_host}:{self.upstream_port}"
                elif lower.startswith("origin:"):
                    line = f"Origin: http://{self.upstream_host}:{self.upstream_port}"
                normalized.append(line)

            target_path = target.partition("?")[0].strip("/")
            if method == "GET" and target_path in self._subpages:
                request_headers: dict[str, str] = {}
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
                    return (
                        status
                        + headers
                        + f"Content-Length: {len(content)}\r\nConnection: close\r\n\r\n"
                    ).encode("latin-1") + content

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


def goto_root(page: Page, base: str) -> None:
    page.goto(base, wait_until="domcontentloaded", timeout=90000)
    page.get_by_role("heading", name=HOME_HEADING, exact=True).wait_for(timeout=90000)
    page.wait_for_timeout(1200)


def navigate(page: Page, base: str, link_name: str, heading: str) -> None:
    goto_root(page, base)
    page.get_by_role("link", name=link_name, exact=True).first.click()
    page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=90000)
    page.wait_for_timeout(1500)


def record_page_state(page: Page, label: str, failures: list[str], overflow: list[str]) -> None:
    text = body(page)
    if any(marker in text for marker in ("Traceback", "Exception", "This app has encountered an error")):
        failures.append(f"{label}: application error visible")
    if dimensions(page)["overflow"] > 1:
        overflow.append(label)


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
    home_text = body(page)
    for report in REPORTS:
        check(report in home_text, f"{name}: Home missing {report}", failures)
    check("Open Reports" in home_text, f"{name}: Home missing report CTA", failures)
    page.screenshot(path=str(SHOTS / f"{name}_home.png"), full_page=True)
    record_page_state(page, "Home", failures, overflow)
    routes.append("Home")

    navigate(page, base, "Reports", REPORT_HEADING)
    report_text = body(page)
    for report in REPORTS:
        check(report in report_text, f"{name}: Reports missing {report}", failures)
    for retired in RETIRED_REPORTS:
        check(retired not in report_text, f"{name}: retired report visible: {retired}", failures)

    for report in REPORTS:
        click_report(page, report)
        text = body(page)
        check("Answer first" in text, f"{name}: {report} missing Answer first", failures)
        check("Complete report" in text, f"{name}: {report} missing complete table", failures)
        check("All-play evidence" in text, f"{name}: {report} missing all-play evidence", failures)
        check("Player evidence" in text, f"{name}: {report} missing player evidence link", failures)
        check("Team evidence" in text, f"{name}: {report} missing team evidence link", failures)
        page.screenshot(
            path=str(SHOTS / f"{name}_{report.lower().replace(' ', '_')}.png"),
            full_page=True,
        )
        record_page_state(page, f"Reports/{report}", failures, overflow)
    routes.append("Reports")

    # Verify an evidence link resolves to the existing supporting player experience.
    click_report(page, "Backfield Control")
    evidence_link = first_visible(page.get_by_role("link", name="Player evidence", exact=True))
    if evidence_link is None:
        failures.append(f"{name}: Player evidence link not clickable")
    else:
        evidence_link.click()
        page.get_by_role("heading", name="Player Role Profile", exact=True).wait_for(timeout=90000)
        page.wait_for_timeout(1500)
        check("Team comparison" in body(page), f"{name}: Player evidence lost supporting context", failures)
        page.screenshot(path=str(SHOTS / f"{name}_player_evidence.png"), full_page=True)
        record_page_state(page, "Player evidence", failures, overflow)
        routes.append("Player evidence")

    navigate(page, base, "Methodology", METHODOLOGY_HEADING)
    methodology_text = body(page)
    for required in (
        "All-play values are authoritative",
        "Backfield Control",
        "Target Hierarchy",
        "Role Movement",
        "Missing-data behavior",
        "What the reports do not claim",
    ):
        check(required in methodology_text, f"{name}: Methodology missing {required}", failures)
    page.screenshot(path=str(SHOTS / f"{name}_methodology.png"), full_page=True)
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
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            mobile = run_viewport(browser, "http://127.0.0.1:8516", 390, 844, "mobile")
            desktop = run_viewport(browser, "http://127.0.0.1:8516", 1440, 900, "desktop")
            browser.close()
    finally:
        proxy.stop()

    payload = {"mobile": mobile, "desktop": desktop}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "browser_results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (OUT / "BROWSER_QA.md").write_text(
        "# Three-Report Browser QA\n\n"
        + "\n".join(
            f"- {name.title()}: {result['status']} · {result['viewport']} · "
            f"overflow {len(result['overflow_failures'])} · "
            f"workflow failures {len(result['workflow_failures'])} · "
            f"console errors {len(result['console_errors'])} · page errors {len(result['page_errors'])}"
            for name, result in payload.items()
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2))
    return 0 if mobile["status"] == desktop["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
