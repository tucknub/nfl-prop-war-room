from __future__ import annotations

from streamlit.testing.v1 import AppTest


def main() -> None:
    app = AppTest.from_file("dashboard/pages/07_Margin_War_Room.py", default_timeout=45)
    app.run()

    if app.exception:
        messages = [str(x.value) for x in app.exception]
        raise AssertionError(f"Margin dashboard raised Streamlit exceptions: {messages}")

    metrics = {str(m.label): str(m.value) for m in app.metric}
    if metrics.get("PICK") != "LAC":
        raise AssertionError(f"Expected live dashboard PICK=LAC, got {metrics.get('PICK')!r}")
    if metrics.get("Opponent") != "ARI":
        raise AssertionError(f"Expected live dashboard opponent ARI, got {metrics.get('Opponent')!r}")
    if metrics.get("Current spread") != "+10.5":
        raise AssertionError(f"Expected current spread +10.5, got {metrics.get('Current spread')!r}")

    # Required operating surfaces should all render in the page body.
    body = "\n".join(str(x.value) for x in app.markdown)
    for required in ["Margin War Room", "Weekly board", "Provisional remaining route", "My pool state", "Data quality"]:
        if required not in body:
            raise AssertionError(f"Missing dashboard section: {required}")

    print("dashboard_streamlit_render=PASS")
    print("dashboard_pick_checksum=LAC")
    print("dashboard_opponent_checksum=ARI")
    print("dashboard_spread_checksum=+10.5")


if __name__ == "__main__":
    main()
