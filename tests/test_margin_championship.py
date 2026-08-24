from scripts.validate_margin_championship import (
    assert_deterministic_simulation,
    assert_override_promotion_policy,
    assert_readiness_guards,
    assert_tie_splitting,
)


def test_championship_readiness_fail_closed() -> None:
    assert_readiness_guards()


def test_championship_tie_share_math() -> None:
    assert_tie_splitting()


def test_championship_base_simulation_is_deterministic_and_ranking_only() -> None:
    assert_deterministic_simulation()


def test_championship_override_requires_threshold_and_independent_confirmation() -> None:
    assert_override_promotion_policy()
