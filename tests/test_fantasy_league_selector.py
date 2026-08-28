from src.fantasy.league_selector import (
    build_sleeper_league_options,
    choose_sleeper_league_label,
)


def test_unique_league_labels_stay_compact():
    leagues = (
        {
            "league_id": "111111111111111111",
            "name": "League A",
            "total_rosters": 10,
            "status": "in_season",
        },
        {
            "league_id": "222222222222222222",
            "name": "League B",
            "total_rosters": 12,
            "status": "pre_draft",
        },
    )

    assert build_sleeper_league_options(leagues) == (
        ("League A · 10 teams", "111111111111111111"),
        ("League B · 12 teams", "222222222222222222"),
    )


def test_duplicate_name_and_team_count_are_disambiguated():
    leagues = (
        {
            "league_id": "1398735222102671360",
            "name": "Franchise Football League",
            "total_rosters": 10,
            "status": "in_season",
        },
        {
            "league_id": "1383849993151987712",
            "name": "Franchise Football League",
            "total_rosters": 10,
            "status": "pre_draft",
        },
    )

    options = build_sleeper_league_options(leagues)

    assert options == (
        (
            "Franchise Football League · 10 teams · In Season · …671360",
            "1398735222102671360",
        ),
        (
            "Franchise Football League · 10 teams · Pre Draft · …987712",
            "1383849993151987712",
        ),
    )
    assert len({label for label, _ in options}) == 2


def test_duplicate_status_still_uses_league_id_suffix():
    leagues = (
        {
            "league_id": "123456789000111111",
            "name": "Same",
            "total_rosters": 10,
            "status": "in_season",
        },
        {
            "league_id": "123456789000222222",
            "name": "Same",
            "total_rosters": 10,
            "status": "in_season",
        },
    )

    options = build_sleeper_league_options(leagues)

    assert options[0][0].endswith("In Season · …111111")
    assert options[1][0].endswith("In Season · …222222")
    assert options[0][0] != options[1][0]


def test_blank_league_ids_are_ignored():
    options = build_sleeper_league_options(
        (
            {
                "league_id": "",
                "name": "Broken",
                "total_rosters": 10,
            },
            {
                "league_id": "333333333333333333",
                "name": "Good",
                "total_rosters": 8,
            },
        )
    )

    assert options == (
        ("Good · 8 teams", "333333333333333333"),
    )


def test_selector_migrates_legacy_demo_choice_to_first_real_league():
    options = {
        "Franchise Football League · 10 teams": "real-1",
        "Papa Johns · 12 teams": "real-2",
        "TEST LEAGUE · 10 teams": "demo-1",
    }

    selected = choose_sleeper_league_label(
        options,
        demo_league_ids={"demo-1"},
        current_label="",
        legacy_label="TEST LEAGUE · 10 teams",
        prefer_real=True,
    )

    assert selected == "Franchise Football League · 10 teams"


def test_selector_respects_intentional_current_demo_choice_after_migration():
    options = {
        "Franchise Football League · 10 teams": "real-1",
        "TEST LEAGUE · 10 teams": "demo-1",
    }

    selected = choose_sleeper_league_label(
        options,
        demo_league_ids={"demo-1"},
        current_label="TEST LEAGUE · 10 teams",
        legacy_label="Franchise Football League · 10 teams",
        prefer_real=True,
    )

    assert selected == "TEST LEAGUE · 10 teams"


def test_selector_can_fall_back_to_demo_when_no_real_league_exists():
    options = {
        "TEST LEAGUE · 10 teams": "demo-1",
    }

    selected = choose_sleeper_league_label(
        options,
        demo_league_ids={"demo-1"},
        legacy_label="TEST LEAGUE · 10 teams",
        prefer_real=False,
    )

    assert selected == "TEST LEAGUE · 10 teams"
