from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("PROPWAR_LIVE_URL", "https://propwar.streamlit.app").rstrip("/")
OUTPUT_DIR = Path(os.environ.get("PROPWAR_LIVE_QA_DIR", "/tmp/propwar-live-qa"))

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
    "margin": ("Margin War Room",),
    "knockout-fantasy": ("Knockout Fantasy",),
}


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


def _capture_diagnostic(page, route: str, body: str) -> None:
    name = (route or "home").replace("-", "_")
    screenshot = OUTPUT_DIR / f"{name}.png"
    body_file = OUTPUT_DIR / f"{name}.txt"
    page.screenshot(path=str(screenshot), full_page=True)
    body_file.write_text(body, encoding="utf-8")
    frame_urls = [frame.url for frame in page.frames]
    print(f"DIAGNOSTIC route=/{route} url={page.url} title={page.title()!r} frames={frame_urls!r}")
    print(body[:3000].replace("\n", " | "))


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
    for heading in expected:
        if _visible_heading(page, heading):
            return
    raise AssertionError(f"{route or '/'} did not render any expected heading: {expected}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        try:
            root_body = _goto(page, "")
            _capture_diagnostic(page, "", root_body)
            _assert_any_heading(page, PUBLIC_HEADINGS[""], "/")
            if "PROP WAR · NFL ROLE INTELLIGENCE · PUBLIC BETA" not in root_body:
                failures.append("Public home is missing the expected PUBLIC BETA identity.")
            if "Owner" not in root_body:
                failures.append("Public home is missing the owner sign-in control.")
            page.screenshot(path=str(OUTPUT_DIR / "home.png"), full_page=True)
        except Exception as exc:
            failures.append(f"Public home failed: {exc}")

        for route, headings in PUBLIC_HEADINGS.items():
            if not route:
                continue
            try:
                route_body = _goto(page, route)
                _capture_diagnostic(page, route, route_body)
                _assert_any_heading(page, headings, route)
            except Exception as exc:
                failures.append(f"Public route /{route} failed: {exc}")

        for route, private_headings in OWNER_ONLY_HEADINGS.items():
            try:
                body = _goto(page, route)
                _capture_diagnostic(page, route, body)
                exposed = []
                for heading in private_headings:
                    if _visible_heading(page, heading):
                        exposed.append(heading)
                if exposed:
                    failures.append(
                        f"Anonymous request to /{route} exposed owner-only heading(s): {exposed}"
                    )
                if "Owner" not in body and "Page not found" not in body and "Latest NFL role research" not in body and "What changed in NFL roles?" not in body:
                    failures.append(
                        f"Anonymous /{route} did not clearly fall back to public/auth-safe content."
                    )
            except Exception as exc:
                failures.append(f"Owner-only route /{route} could not be checked safely: {exc}")

        browser.close()

    if failures:
        print("LIVE STREAMLIT QA FAILURES")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("live_streamlit_public_home=PASS")
    print("live_streamlit_public_routes=PASS")
    print("live_streamlit_owner_routes_hidden_anonymous=PASS")
    print(f"live_streamlit_origin={BASE_URL}")


if __name__ == "__main__":
    main()
