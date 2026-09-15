from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("PROPWAR_LIVE_URL", "https://propwar.streamlit.app").rstrip("/")
OUTPUT_DIR = Path(os.environ.get("PROPWAR_LIVE_QA_DIR", "/tmp/propwar-live-qa")) / "release"

PUBLIC_HEADINGS = {
    "": ("Latest NFL role research", "What changed in NFL roles?"),
    "reports": ("NFL Role Intelligence",),
    "teams": ("Team Role Breakdown",),
    "players": ("Player Role Profile",),
    "games": ("Game Usage Review",),
    "methodology": ("Methodology",),
}

OWNER_ONLY_HEADINGS = {
    "glitch-radar": ("Markets",),
    "fantasy-hq": ("Fantasy HQ",),
    "deep-prop-radar": ("Market Research",),
    "margin": ("Margin War Room",),
    "knockout": ("Knockout Fantasy War Room",),
}

PRIVATE_MARKERS = (
    "PROP WAR · NFL DECISION INTELLIGENCE · PRIVATE BETA",
    "private authoritative state loaded",
)


def _published_expectations() -> tuple[str | None, str | None]:
    root = Path(__file__).resolve().parents[1]
    candidates: list[dict[str, object]] = []
    for path in sorted((root / "outputs" / "role_research").glob("role_research_status_*.json")):
        try:
            candidates.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            continue
    if not candidates:
        return None, None
    latest = max(candidates, key=lambda item: int(item.get("season") or 0))
    season = latest.get("season")
    week = latest.get("published_through_week")
    if str(latest.get("status") or "") != "PUBLISHED" or season is None or week is None:
        return None, None
    return (
        f"{season} current-season data published through Week {week}.",
        f"Data through {season} Week {week}",
    )


def _body(page) -> str:
    texts: list[str] = []
    for frame in page.frames:
        try:
            text = frame.locator("body").inner_text(timeout=10_000).strip()
        except Exception:
            continue
        if text and text not in texts:
            texts.append(text)
    return "\n\n".join(texts)


def _goto(page, route: str) -> str:
    url = BASE_URL if not route else f"{BASE_URL}/{route}"
    page.goto(url, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(5_000)
    return _body(page)


def _visible_heading(page, heading: str) -> bool:
    for frame in page.frames:
        try:
            locator = frame.get_by_role("heading", name=heading, exact=True)
            if locator.count() and locator.first.is_visible():
                return True
        except Exception:
            continue
    return False


def _assert_any_heading(page, expected: tuple[str, ...], route: str) -> None:
    if not any(_visible_heading(page, heading) for heading in expected):
        raise AssertionError(f"/{route} missing expected heading {expected!r}")


def _capture(page, route: str, body: str) -> None:
    name = (route or "home").replace("-", "_")
    page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=True)
    (OUTPUT_DIR / f"{name}.txt").write_text(body, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    expected_status, expected_data_label = _published_expectations()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        for route, headings in PUBLIC_HEADINGS.items():
            try:
                body = _goto(page, route)
                _capture(page, route, body)
                _assert_any_heading(page, headings, route)
                if not route and expected_status and expected_status not in body:
                    failures.append(f"Home is stale: expected {expected_status!r}.")
                if route == "games" and expected_data_label and expected_data_label not in body:
                    failures.append(f"Games is stale: expected {expected_data_label!r}.")
            except Exception as exc:
                failures.append(f"Public /{route} failed: {exc}")

        for route, headings in OWNER_ONLY_HEADINGS.items():
            try:
                body = _goto(page, route)
                _capture(page, route, body)
                exposed = [heading for heading in headings if _visible_heading(page, heading)]
                if exposed:
                    failures.append(f"Anonymous /{route} exposed owner heading(s): {exposed}")
                markers = [marker for marker in PRIVATE_MARKERS if marker in body]
                if markers:
                    failures.append(f"Anonymous /{route} exposed private marker(s): {markers}")
            except Exception as exc:
                failures.append(f"Owner-only /{route} could not be checked: {exc}")

        browser.close()

    if failures:
        print("LIVE STREAMLIT RELEASE QA FAILURES")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("live_streamlit_public_routes=PASS")
    print("live_streamlit_current_role_data=PASS")
    print("live_streamlit_owner_routes_hidden_anonymous=PASS")
    print(f"live_streamlit_origin={BASE_URL}")


if __name__ == "__main__":
    main()
