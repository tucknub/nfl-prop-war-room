from scripts.validate_margin_championship import (
    assert_deterministic_simulation,
    assert_readiness_guards,
    assert_tie_splitting,
)


def test_championship_readiness_fail_closed() -> None:
    assert_readiness_guards()


def test_championship_tie_share_math() -> None:
    assert_tie_splitting()


def test_championship_simulation_is_deterministic_and_non_authoritative() -> None:
    assert_deterministic_simulation()
