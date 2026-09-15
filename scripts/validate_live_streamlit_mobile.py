from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("PROPWAR_LIVE_URL", "https://propwar.streamlit.app").rstrip("/")
OUTPUT_DIR = Path(os.environ.get("PROPWAR_LIVE_QA_DIR", "/tmp/propwar-live-qa")) / "mobile"

PUBLIC_ROUTES = {
    "": ("What changed in NFL roles?", "Latest NFL role research"),
    "reports": ("NFL Role Intelligence",),
    "players": ("Player Role Profile",),
    "games": ("Game Usage Review",),
}

EXPANDER_EXPECTATIONS = {
    "reports": ("Customize report", ("Season", "Window")),
    "players": ("Change season", ("Season",)),
    "games": ("Change game", ("Season", "Week", "Game")),
}

WEEK_ONE_BASELINE_MARKER = "Week 1 establishes the in-season baseline"


def _published_expectations() -> tuple[str | None, str | None, int | None]:
    root = Path(__file__).resolve().parents[1]
    candidates: list[dict[str, object]] = []
    for path in sorted((root / "outputs" / "role_research").glob("role_research_status_*.json")):
        try:
            candidates.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            continue
    if not candidates:
        return None, None, None
    latest = max(candidates, key=lambda item: int(item.get("season") or 0))
    season = latest.get("season")
    week = latest.get("published_through_week")
    if str(latest.get("status") or "") != "PUBLISHED" or season is None or week is None:
        return None, None, None
    return (
        f"{season} current-season data published through Week {week}.",
        f"Data through {season} Week {week}",
        int(week),
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
    page.wait_for_timeout(7_000)
    return _body(page)


def _assert_heading(page, expected: tuple[str, ...], route: str) -> None:
    for frame in page.frames:
        for heading in expected:
            try:
                locator = frame.get_by_role("heading", name=heading, exact=True)
                if locator.count() and locator.first.is_visible():
                    return
            except Exception:
                continue
    raise AssertionError(f"/{route} missing expected mobile heading {expected!r}")


def _assert_no_document_overflow(page, route: str) -> None:
    checked = 0
    problems: list[str] = []
    for frame in page.frames:
        if not frame.url.startswith(BASE_URL):
            continue
        try:
            metrics = frame.evaluate(
                """() => ({
                    viewport: window.innerWidth,
                    doc: document.documentElement ? document.documentElement.scrollWidth : 0,
                    body: document.body ? document.body.scrollWidth : 0
                })"""
            )
        except Exception:
            continue
        checked += 1
        viewport = int(metrics.get("viewport") or 0)
        widest = max(int(metrics.get("doc") or 0), int(metrics.get("body") or 0))
        if viewport and widest > viewport + 8:
            problems.append(f"frame={frame.url} viewport={viewport} scrollWidth={widest}")
    if checked == 0:
        raise AssertionError(f"/{route} had no PropWar frame available for overflow audit")
    if problems:
        raise AssertionError(f"/{route} has document-level horizontal overflow: {'; '.join(problems)}")


def _exercise_expander(page, route: str, label: str, expected_tokens: tuple[str, ...]) -> None:
    for frame in page.frames:
        try:
            details = frame.locator('[data-testid="stExpander"]').filter(has_text=label)
            if not details.count():
                continue
            summary = details.first.locator("summary")
            if not summary.count() or not summary.first.is_visible():
                continue
            summary.first.click(timeout=10_000)
            page.wait_for_timeout(1_000)
            body = _body(page)
            missing = [token for token in expected_tokens if token not in body]
            if missing:
                raise AssertionError(
                    f"/{route} mobile control {label!r} missing fields {missing!r}"
                )
            return
        except AssertionError:
            raise
        except Exception:
            continue
    raise AssertionError(f"/{route} could not open mobile control {label!r}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    expected_status, expected_data_label, published_week = _published_expectations()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for route, headings in PUBLIC_ROUTES.items():
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=3,
                is_mobile=True,
                has_touch=True,
            )
            page = context.new_page()
            try:
                body = _goto(page, route)
                _assert_heading(page, headings, route)
                if "Role Intelligence" not in body:
                    failures.append(f"/{route} mobile header/navigation identity is missing.")
                if not route:
                    if expected_status and expected_status not in body:
                        failures.append(f"Mobile home is stale: expected {expected_status!r}.")
                    if published_week == 1 and WEEK_ONE_BASELINE_MARKER not in body:
                        failures.append(
                            "Mobile home is missing the Week 1 baseline explanation, so the deployed UI code is stale."
                        )
                elif expected_data_label and expected_data_label not in body:
                    failures.append(f"/{route} is stale on mobile: expected {expected_data_label!r}.")

                _assert_no_document_overflow(page, route)
                page.screenshot(
                    path=str(OUTPUT_DIR / f"{route or 'home'}.png"),
                    full_page=True,
                )

                if route in EXPANDER_EXPECTATIONS:
                    label, tokens = EXPANDER_EXPECTATIONS[route]
                    _exercise_expander(page, route, label, tokens)
                    page.screenshot(
                        path=str(OUTPUT_DIR / f"{route}_controls.png"),
                        full_page=True,
                    )
            except Exception as exc:
                failures.append(f"/{route or ''} mobile audit failed: {exc}")
            finally:
                context.close()

        browser.close()

    if failures:
        print("LIVE STREAMLIT MOBILE QA FAILURES")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("live_streamlit_mobile_routes=PASS")
    print("live_streamlit_mobile_controls=PASS")
    print("live_streamlit_mobile_overflow=PASS")
    print("live_streamlit_mobile_current_ui=PASS")
    print(f"live_streamlit_mobile_origin={BASE_URL}")


if __name__ == "__main__":
    main()
