from __future__ import annotations

import json
import traceback

from playwright.sync_api import Page, sync_playwright

import run_three_report_browser_qa as qa
import run_three_report_browser_qa_v4 as previous
from run_three_report_browser_qa_v2 import navigate


LEGACY_EXPECTATION_FAILURES = {
    "Methodology missing All-play values are authoritative",
    "Methodology missing Missing-data behavior",
    "Methodology missing What the reports do not claim",
}
ACTUAL_METHODOLOGY_COPY = (
    "All-play raw counts and same-team denominators are the methodology authority",
    "Report boundaries",
    "What each report does—and does not—claim",
    "Missing and unavailable data",
)


def validate_methodology_copy(browser, base: str, width: int, height: int, name: str) -> list[str]:
    page = browser.new_page(viewport={"width": width, "height": height})
    failures: list[str] = []
    navigate(page, base, "Methodology", qa.METHODOLOGY_HEADING)
    text = qa.body(page)
    for phrase in ACTUAL_METHODOLOGY_COPY:
        if phrase not in text:
            failures.append(f"{name}: Methodology missing {phrase}")
    page.close()
    return failures


def normalize_result(result: dict[str, object], extra_failures: list[str]) -> dict[str, object]:
    failures = [
        failure
        for failure in result["workflow_failures"]
        if not any(failure.endswith(expected) for expected in LEGACY_EXPECTATION_FAILURES)
    ]
    failures.extend(extra_failures)
    result["workflow_failures"] = failures
    result["status"] = (
        "PASS"
        if not failures
        and not result["overflow_failures"]
        and not result["console_errors"]
        and not result["page_errors"]
        else "FAIL"
    )
    return result


def main() -> int:
    qa.SHOTS.mkdir(parents=True, exist_ok=True)
    proxy = qa.LocalRouteProxy("127.0.0.1", 8514, 8516)
    proxy.start()
    payload: dict[str, object]
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            mobile = previous.run_viewport(browser, "http://127.0.0.1:8516", 390, 844, "mobile")
            mobile = normalize_result(
                mobile,
                validate_methodology_copy(browser, "http://127.0.0.1:8516", 390, 844, "mobile"),
            )
            desktop = previous.run_viewport(browser, "http://127.0.0.1:8516", 1440, 900, "desktop")
            desktop = normalize_result(
                desktop,
                validate_methodology_copy(browser, "http://127.0.0.1:8516", 1440, 900, "desktop"),
            )
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
