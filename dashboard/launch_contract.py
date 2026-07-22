from __future__ import annotations

REPORT_ORDER: tuple[str, ...] = (
    "Backfield Control",
    "Target Hierarchy",
    "Role Movement",
)

REPORT_DEFINITIONS: dict[str, str] = {
    "Backfield Control": (
        "Which running backs control carries and total backfield opportunities for their teams?"
    ),
    "Target Hierarchy": (
        "Which wide receivers and tight ends control their teams' documented targets?"
    ),
    "Role Movement": (
        "Which player shares changed most versus the prior matching window, and what raw counts produced the change?"
    ),
}

REPORT_FAMILIES: dict[str, tuple[str, ...]] = {
    "Backfield Control": ("rb_carry_share", "rb_opportunity_share"),
    "Target Hierarchy": ("wr_target_share", "te_target_share"),
    "Role Movement": (
        "rb_carry_share",
        "rb_opportunity_share",
        "wr_target_share",
        "te_target_share",
    ),
}

REPORT_METHODS: dict[str, tuple[str, ...]] = {
    "Backfield Control": (
        "Carries and total RB opportunities are separate closed views.",
        "All-play player counts are divided by the matching same-team all-play denominator.",
        "Normal-game share is supporting context and never replaces the all-play authority value.",
    ),
    "Target Hierarchy": (
        "WR and TE target groups are the only launch target views.",
        "All-play targets are divided by the matching same-team all-play target denominator.",
        "Unavailable route or first-read fields are not estimated or displayed.",
    ),
    "Role Movement": (
        "Current-window raw counts are summed before share is calculated.",
        "The comparison uses the immediately preceding matching window.",
        "Movement is descriptive and does not claim that the role will persist.",
    ),
}

ALL_PLAY_AUTHORITY_NOTICE = (
    "All-play raw counts and same-team denominators are the methodology authority. "
    "Normal-game values are supporting context only."
)
