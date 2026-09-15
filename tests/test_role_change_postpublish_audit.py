from scripts.audit_role_change_signals import audit_role_change_signals


def test_week_one_role_change_audit_is_explicitly_skipped() -> None:
    payload = audit_role_change_signals(2026, 1)

    assert payload["status"] == "SKIPPED"
    assert payload["week"] == 1
    assert "baseline" in str(payload["message"]).lower()


def test_historical_week_two_role_change_audit_passes_real_data() -> None:
    payload = audit_role_change_signals(2025, 2)

    assert payload["status"] == "PASS", payload
    assert payload["week"] == 2
    assert isinstance(payload["top_signals"], list)
    assert all(check["passed"] for check in payload["checks"]), payload["checks"]
