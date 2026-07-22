from __future__ import annotations

import json
import traceback
from pathlib import Path

from playwright.sync_api import Page

import run_three_report_browser_qa as qa


ROUTES = {
    "Reports": "reports",
    "Methodology": "methodology",
}


def navigate(page: Page, base: str, link_name: str, heading: str) -> None:
    """Navigate through the hidden mobile sidebar using the proven route href method."""
    qa.goto_root(page, base)
    route = ROUTES[link_name]
    locator = page.locator(f'a[href="{base}/{route}"]')
    if locator.count() == 0:
        locator = page.locator(f'a[href="/{route}"]')
    if locator.count() == 0:
        raise RuntimeError(f"Navigation link not found for {link_name}: {route}")
    locator.first.evaluate("element => element.click()")
    page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=90000)
    page.wait_for_timeout(1500)


def main() -> int:
    qa.navigate = navigate
    try:
        return qa.main()
    except Exception as error:
        qa.OUT.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "CRASH",
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        (qa.OUT / "browser_crash.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        (qa.OUT / "browser_crash.txt").write_text(payload["traceback"], encoding="utf-8")
        print(payload["traceback"])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
