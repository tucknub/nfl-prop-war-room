# Weekly Role Report Calibration Rules

- Baseline calculations remain count-weighted and use only earlier same-season, same-team qualifying games.
- Week 2 uses Week 1 only; Week 3 can use only two prior games. Exact sample counts remain visible.
- A reciprocal transfer requires at least one qualified gain and one qualified loss for the same season, week, team, and role family. The primary player is the gainer with the largest increase, then larger current raw count, larger team denominator, and alphabetical name.
- Reciprocal situations are ordered before individual situations within the same category; the standard absolute-change, raw-count, team-denominator, and name tie-break follows.
- A default team-role family appears once. A team may occupy at most 2 default cards across clearly different families.
- Within a category, one backfield and one target situation are reserved when both consolidated situation groups qualify. Remaining capacity follows deterministic rank. Empty capacity may be filled by the other group.
- The Overstated screen uses a 10% all-plays/normal gap, at least 2 outside-normal opportunities, and a team denominator of at least 10; it does not reuse a role-volume floor that can suppress the abnormal-context evidence itself.
- Collapsed All-plays share is shown for Overstated cards or when the absolute gap is at least 5%.
- Context evidence is limited to 2 facts and uses these `(player count, team denominator)` minimums: (('inside_5', 1, 1), ('red_zone', 2, 2), ('passing_down', 2, 5), ('early_down', 3, 8)).
- Strong-opportunity production rates are yards/carry for RB carry share, yards/touch for RB opportunity share, and receiving yards/target for WR/TE target share.
- No weighted or universal score is calculated. No candidate was manually removed.
