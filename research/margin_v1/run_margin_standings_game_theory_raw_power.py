from __future__ import annotations

import run_margin_standings_game_theory as game_theory


def _disable_style_predictions(*_args, **_kwargs):
    """Force every future-line lookup to the raw long/slow fallback.

    The underlying standings experiment is intentionally left otherwise unchanged
    so this is a paired model-input test rather than a redesigned game-theory test.
    """
    return {}


def main() -> None:
    game_theory.strat.train_future_predictions = _disable_style_predictions
    print("=== PRODUCTION-ALIGNED CHAMPIONSHIP GATE: STYLE DISABLED ===")
    print("future_model=raw_long_slow_market_power")
    print("style_lookup=forced_empty")
    print("all other standings-game-theory settings unchanged")
    game_theory.main()


if __name__ == "__main__":
    main()
